"""Run with: python -m unittest -v"""
import json
import io
from pathlib import Path
import tempfile
import unittest
import threading
from unittest.mock import patch
import app


class ArchiveChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data = app.DATA
        app.DATA = Path(self.tmp.name)
        app.init()

    def tearDown(self):
        app.DATA = self.old_data
        self.tmp.cleanup()

    def test_doi_dedup_keeps_online_date_and_personal_records(self):
        date = app.dt.datetime.now(app.UTC8).date().isoformat()
        y, m, d = map(int, date.split('-'))
        item = {'DOI':'10.1109/TEST.1', 'title':['Neural fault diagnosis for power converters'],
                'published-online':{'date-parts':[[y,m,d]]}}
        self.assertEqual(app.save_item(item,'TPEL',True),1)
        with app.db() as c:
            c.execute("UPDATE papers SET favorite=1,read=1 WHERE id='10.1109/test.1'")
        formal = dict(item)
        del formal['published-online']
        formal['published-print']={'date-parts':[[y,m,d]]}
        self.assertEqual(app.save_item(formal,'TPEL'),0)
        p=app.snapshot()['papers'][0]
        self.assertEqual((p['favorite'],p['read'],p['date_basis']),(1,1,'首次在线日期'))
        self.assertEqual(len(app.snapshot()['papers']),1)

    def test_daily_crossref_checks_beijing_today_and_skips_old_new_records(self):
        current = app.dt.datetime.now(app.UTC8).date()
        older = current - app.dt.timedelta(days=30)
        def record(doi, date):
            return {'DOI':doi, 'title':['Neural fault diagnosis for power converters'],
                    'published-online':{'date-parts':[[date.year,date.month,date.day]]}}
        response = {'message':{'items':[record('10.1109/TEST.OLD',older),record('10.1109/TEST.NEW',current)],
                               'total-results':2,'next-cursor':'ignored'}}
        urls = []
        def fetch(url):
            urls.append(url)
            return json.dumps(response)
        with patch.object(app,'request',side_effect=fetch):
            app.collect_crossref(app.JOURNALS[0])
        self.assertEqual(len(urls),1)
        self.assertIn('from-update-date',urls[0])
        self.assertIn('until-update-date',urls[0])
        with app.db() as c:
            self.assertIsNone(c.execute("SELECT id FROM papers WHERE id='10.1109/test.old'").fetchone())
            self.assertIsNotNone(c.execute("SELECT id FROM papers WHERE id='10.1109/test.new'").fetchone())

    def test_full_scan_can_backfill_old_record(self):
        older = app.dt.datetime.now(app.UTC8).date() - app.dt.timedelta(days=30)
        item = {'DOI':'10.1109/TEST.OLD', 'title':['Neural fault diagnosis for power converters'],
                'published-online':{'date-parts':[[older.year,older.month,older.day]]}}
        self.assertEqual(app.save_item(item,'TIE',allow_historical_new=False),0)
        self.assertEqual(app.save_item(item,'TIE',allow_historical_new=True),1)
        with app.db() as c:
            self.assertEqual(c.execute("SELECT backfill FROM papers WHERE id='10.1109/test.old'").fetchone()[0],1)

    def test_scope_digital_twin_needs_ai_and_no_grid(self):
        self.assertIsNone(app.classify('A digital twin of a DC converter','','TPEL'))
        result=app.classify('Neural digital twin for inverter fault diagnosis','','TPEL')
        self.assertIn('数字孪生',result[0])
        self.assertTrue(result[1])
        self.assertIsNone(app.classify('Deep learning electricity price forecasting','','TII'))
        self.assertIsNone(app.classify('Neural bearing fault diagnosis in rotating machinery','','TIE'))
        self.assertIsNone(app.classify('High efficiency GaN inverter with a planar transformer','','TPEL'))
        self.assertIsNone(app.classify('Local data-driven fault localization for DC microgrid','','TPEL'))
        self.assertIsNone(app.classify('热电燃烧系统数字孪生建模与运行优化','通过神经网络预测燃煤发电机能耗','CSEE'))
        self.assertIsNone(app.classify('Neural anomaly detection in industrial production','A motor converter is discussed in related work','TII'))
        self.assertIsNone(app.classify('READ3D-Net: GAN-Based Convolutional Network for Anomaly Detection','','TII'))
        self.assertIsNone(app.classify('Deep Reinforcement Learning for Inverter Volt-Var Control in Distribution Networks','','TII'))
        self.assertIsNone(app.classify('Intelligent power module with current sensors','','TPEL'))
        self.assertIsNone(app.classify('Reinforcement learning for robot visual servoing','','TIE'))
        self.assertIsNone(app.classify('Neural welding of aluminum coil','','TII'))
        self.assertIsNone(app.classify('Memristor neural network circuit with learning','','TII'))
        self.assertFalse(app.classify('Neural fault-tolerant control for inverter','','TPEL')[1])

    def test_reopening_reuses_server_and_triggers_update(self):
        server = app.LocalServer(("127.0.0.1", 0), app.Handler)
        server.token = "integration-test-local-token"
        (app.DATA / "access-token.txt").write_text(server.token, encoding="utf-8")
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        updated = threading.Event()
        try:
            with patch.dict(app.CONFIG, {"port": server.server_port}), patch("sys.argv", ["app.py", "--no-browser"]), patch.object(app, "run_update", updated.set), patch.object(app.logging, "basicConfig"):

                app.main()
                self.assertTrue(updated.wait(3), "Reopening should request an update from the existing server")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(3)

    def test_metadata_update_never_calls_ai(self):
        with patch.object(app, "collect_crossref"), patch.object(app, "collect_csee"), patch.object(app, "collect_ces"), patch.object(app, "collect_aas"), patch.object(app, "enrich_abstracts"), patch.object(app, "enrich_ai") as generate, patch.object(app, "local_ai_provider") as provider:
            app.run_update()
            generate.assert_not_called()
            provider.assert_not_called()
        self.assertFalse(app.STATE["running"])

    def test_empty_archive_bootstraps_then_uses_daily_updates(self):
        with patch.object(app, "collect_crossref") as crossref, patch.object(app, "collect_csee"), \
             patch.object(app, "collect_ces"), patch.object(app, "collect_aas"), patch.object(app, "enrich_abstracts"):
            app.run_update()
            self.assertTrue(all(call.kwargs.get('full') for call in crossref.call_args_list))
            current = app.dt.datetime.now(app.UTC8).date()
            item = {'DOI':'10.1109/TEST.BOOTSTRAP', 'title':['Neural fault diagnosis for power converters'],
                    'published-online':{'date-parts':[[current.year,current.month,current.day]]}}
            app.save_item(item,'TPEL')
            crossref.reset_mock()
            app.run_update()
            self.assertTrue(all(call.kwargs.get('full') is False for call in crossref.call_args_list))

    def test_no_pending_records_do_not_call_ai(self):
        with patch.object(app, "enrich_ai") as generate, patch.object(app, "local_ai_provider") as provider:
            app.run_enrich()
            generate.assert_not_called()
            provider.assert_not_called()
        self.assertIn("未调用 AI", app.STATE["ai"])

    def test_refused_local_proxy_retries_public_metadata_directly(self):
        response = io.BytesIO(b'{"ok":true}')
        response.headers = type("Headers", (), {"get_content_type": lambda self: "application/json"})()
        response.url = "https://example.org/works"
        direct = type("Direct", (), {"open": lambda self, req, timeout: response})()
        refused = app.urllib.error.URLError(ConnectionRefusedError("proxy refused"))
        with patch.object(app.urllib.request, "urlopen", side_effect=refused), \
             patch.object(app.urllib.request, "getproxies", return_value={"https": "http://127.0.0.1:10810"}), \
             patch.object(app.urllib.request, "build_opener", return_value=direct):
            self.assertEqual(app.request("https://example.org/works", retries=0), '{"ok":true}')

    def test_crossref_uses_verified_direct_connection_first(self):
        response = io.BytesIO(b'{"ok":true}')
        response.headers = type("Headers", (), {"get_content_type": lambda self: "application/json"})()
        response.url = "https://api.crossref.org/works"
        direct = type("Direct", (), {"open": lambda self, req, timeout: response})()
        with patch.object(app.urllib.request, "urlopen", side_effect=AssertionError("proxy should not be used")), \
             patch.object(app.urllib.request, "build_opener", return_value=direct):
            self.assertEqual(app.request("https://api.crossref.org/works", retries=0), '{"ok":true}')

    def test_missing_online_date_does_not_use_registration_date(self):
        date,basis,precision=app.publication({'created':{'date-parts':[[2026,10,20]]},'issued':{'date-parts':[[2025]]}})
        self.assertEqual(date,'2025-01-01')
        self.assertEqual(precision,'年')
        self.assertIn('在线日期缺失',basis)

    def test_aas_uses_explicit_first_online_date(self):
        current = app.dt.datetime.now(app.UTC8).date()
        printed = current + app.dt.timedelta(days=10)
        listing = '<a href="/cn/article/doi/10.16383/j.aas.test">基于神经网络的逆变器故障诊断</a>'
        detail = (f'<meta name="citation_title" content="基于神经网络的逆变器故障诊断">'
                  f'<meta name="citation_doi" content="10.16383/j.aas.test">'
                  f'<meta name="citation_date" content="{printed.isoformat()}">'
                  f'<li><b>网络出版日期:&nbsp;</b><span>{current.isoformat()}</span></li>'
                  '<div class="article-abstract"><b>摘要:</b> 本文通过神经网络检测逆变器开关故障。</div>')
        def fetch(url, **kwargs):
            return detail if '/cn/article/doi/' in url else listing
        with patch.object(app, 'request', side_effect=fetch):
            app.collect_aas(next(j for j in app.JOURNALS if j['id']=='AAS'))
        with app.db() as c:
            row = c.execute("SELECT published,date_basis FROM papers WHERE journal='AAS'").fetchone()
            self.assertEqual((row['published'],row['date_basis']), (current.isoformat(),'首次在线日期'))

    def test_publisher_metadata_and_multiline_links(self):
        p=app.JournalHTML()
        p.feed('<b>神经网络逆变器故障诊断</b><a href="../abstract/abstract1.shtml">摘要</a><a href=\nvolumn_1551.shtml>上一期</a>')
        self.assertEqual(p.links[0][1],'神经网络逆变器故障诊断')
        self.assertEqual(p.links[1][0],'volumn_1551.shtml')


if __name__=='__main__':
    unittest.main()
