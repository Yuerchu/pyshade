"""cases_from_raw:JS 回传的 case 逐条校验,一条坏数据不炸掉整份报告(零 pytauri 依赖)。"""

from pyshade.testing._harness import cases_from_raw


class TestCasesFromRaw:
    def test_valid_cases_pass_through(self) -> None:
        raw = [{'id': 'headers.fidelity', 'status': 'pass', 'source': 'js'}]
        cases = cases_from_raw(raw)
        assert len(cases) == 1
        assert cases[0].id == 'headers.fidelity'
        assert cases[0].status == 'pass'

    def test_invalid_case_degrades_to_error(self) -> None:
        raw = [
            {'id': 'good.case', 'status': 'pass', 'source': 'js'},
            {'status': 42},  # 字段类型跑偏:此前 ValidationError 会让整份 report.json 都写不出来
        ]
        cases = cases_from_raw(raw)
        assert len(cases) == 2
        assert cases[0].id == 'good.case'
        assert cases[1].id == 'harness.invalid_case'
        assert cases[1].status == 'error'
        assert '42' in str(cases[1].detail.get('raw', ''))
