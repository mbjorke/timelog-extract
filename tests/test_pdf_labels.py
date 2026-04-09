"""Regression tests for English PDF labels."""

import unittest

from outputs import pdf


class PdfLabelTests(unittest.TestCase):
    def test_title_and_main_labels_are_english(self):
        self.assertEqual(pdf.PDF_TITLE, "Time report - invoice basis")
        self.assertEqual(pdf.PDF_LABEL_PERIOD, "Period")
        self.assertEqual(pdf.PDF_LABEL_CUSTOMER, "Customer")
        self.assertEqual(pdf.PDF_LABEL_PROJECTS, "Projects")
        self.assertEqual(pdf.PDF_LABEL_TOTAL_BILLABLE, "Total billable")
        self.assertEqual(pdf.PDF_LABEL_RAW_TIME, "Raw time in period")
        self.assertEqual(pdf.PDF_LABEL_TOTAL_ESTIMATED, "Total estimated")

    def test_table_and_daily_labels_are_english(self):
        self.assertEqual(pdf.PDF_TABLE_HEADER_SERVICE, "Description of service / deliverable")
        self.assertEqual(pdf.PDF_TABLE_HEADER_SCOPE, "Scope")
        self.assertEqual(pdf.PDF_SUMMARY_ROW, "Total")
        self.assertEqual(pdf.PDF_DAILY_DATE, "Date")
        self.assertEqual(pdf.PDF_DAILY_HOURS, "Hours")
        self.assertEqual(pdf.PDF_DAILY_SPEC, "Daily breakdown")

    def test_fallback_prose_is_english(self):
        self.assertEqual(
            pdf.PDF_FALLBACK_DESCRIPTION,
            "Ongoing implementation, analysis, and delivery within the project.",
        )
        self.assertEqual(pdf.PDF_FALLBACK_SOURCE, "local work logs")
        self.assertEqual(pdf.PDF_FALLBACK_EXAMPLES, "Ongoing implementation, analysis, and iteration.")
        self.assertEqual(
            pdf.PDF_FALLBACK_PROJECT_SUMMARY_TEMPLATE,
            "Ongoing work in the project, summarized from {source}. Examples of delivered effort: {examples}",
        )


if __name__ == "__main__":
    unittest.main()
