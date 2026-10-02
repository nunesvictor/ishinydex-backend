from django.test import SimpleTestCase

from home.utils import col_choices, row_choices


class ChoicesTests(SimpleTestCase):
    def test_row_and_col_choices_are_one_based_labels(self):
        self.assertEqual(
            list(row_choices()), [(0, "1"), (1, "2"), (2, "3"), (3, "4"), (4, "5")]
        )
        self.assertEqual(len(list(col_choices())), 6)
        self.assertEqual(list(col_choices())[-1], (5, "6"))
