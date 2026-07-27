import unittest
from unittest.mock import patch

import flash_report


class CrmProjectResolutionTests(unittest.TestCase):
    def _index(self, rows):
        return flash_report._build_crm_project_index(rows)

    def test_resolves_exact_do_before_conflicting_fio(self):
        index = self._index([
            {
                'case_id': 1,
                'do_number': '18-0006-1c-004870',
                'debtor_name': 'Грузан Олег Александрович',
                'project': '(DCA) BIB',
            },
            {
                'case_id': 2,
                'do_number': 'ДО-2',
                'debtor_name': 'Иванова Елена Петровна',
                'project': '(DCA) OTP',
            },
        ])

        result = flash_report.resolve_crm_project(
            'Оплата по ДО 18-0006-1C-004870, СПИ Иванова Елена Петровна',
            index,
        )

        self.assertEqual('do', result['match_type'])
        self.assertEqual('(DCA) BIB', result['project'])
        self.assertEqual(1, result['case_id'])

    def test_resolves_fio_ignoring_case_punctuation_and_yo(self):
        index = self._index([
            {
                'case_id': 7,
                'do_number': 'ДО-7',
                'debtor_name': 'Фёдорова Елена Владимировна',
                'project': '(DCA) Unicredit',
            },
        ])

        result = flash_report.resolve_crm_project(
            'Взыскан долг с ФЕДОРОВА, ЕЛЕНА ВЛАДИМИРОВНА. НДС нет',
            index,
        )

        self.assertEqual('fio', result['match_type'])
        self.assertEqual('(DCA) Unicredit', result['project'])

    def test_does_not_guess_when_same_fio_has_different_projects(self):
        index = self._index([
            {
                'case_id': 10,
                'do_number': 'ДО-10',
                'debtor_name': 'Иванов Иван Иванович',
                'project': '(DCA) BIB',
            },
            {
                'case_id': 11,
                'do_number': 'ДО-11',
                'debtor_name': 'Иванов Иван Иванович',
                'project': '(DCA) OTP',
            },
        ])

        result = flash_report.resolve_crm_project(
            'Погашение долга Иванов Иван Иванович',
            index,
        )

        self.assertTrue(result['matched'])
        self.assertTrue(result['ambiguous'])
        self.assertIsNone(result['project'])

    def test_does_not_use_mapped_project_for_same_fio_with_unmapped_case(self):
        index = self._index([
            {
                'case_id': 10,
                'do_number': 'ДО-10',
                'debtor_name': 'Иванов Иван Иванович',
                'project': '(DCA) BIB',
            },
            {
                'case_id': 11,
                'do_number': 'ДО-11',
                'debtor_name': 'Иванов Иван Иванович',
                'project': None,
            },
        ])

        result = flash_report.resolve_crm_project(
            'Погашение долга Иванов Иван Иванович',
            index,
        )

        self.assertTrue(result['ambiguous'])
        self.assertIsNone(result['project'])

    def test_short_numeric_do_requires_a_label(self):
        index = self._index([
            {
                'case_id': 12,
                'do_number': '12345',
                'debtor_name': 'Петров Петр Петрович',
                'project': '(DCA) AB',
            },
        ])

        incidental = flash_report.resolve_crm_project(
            'Сумма 12345 рублей без НДС',
            index,
        )
        labelled = flash_report.resolve_crm_project(
            'Оплата по договору 12345 без НДС',
            index,
        )

        self.assertFalse(incidental['matched'])
        self.assertEqual('(DCA) AB', labelled['project'])

    @patch('flash_report.execute_values')
    @patch('flash_report.query')
    def test_batch_updates_only_resolved_receipts(self, query_mock, execute_values_mock):
        query_mock.return_value = [
            {'id': 101, 'purpose_text': 'Долг с Сидоров Сидор Сидорович', 'Проект': '(DP) Old'},
            {'id': 102, 'purpose_text': 'Прочее поступление', 'Проект': '(DP) Keep'},
        ]
        index = self._index([
            {
                'case_id': 20,
                'do_number': 'ДО-20',
                'debtor_name': 'Сидоров Сидор Сидорович',
                'project': '(DCA) New',
            },
        ])

        stats = flash_report.apply_crm_projects(
            period=None,
            crm_index=index,
        )

        self.assertEqual(2, stats['scanned'])
        self.assertEqual(1, stats['matched'])
        self.assertEqual(1, stats['with_project'])
        self.assertEqual(1, stats['updated'])
        execute_values_mock.assert_called_once()
        self.assertEqual([('(DCA) New', 101)], execute_values_mock.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
