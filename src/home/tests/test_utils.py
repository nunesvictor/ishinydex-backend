from django.test import SimpleTestCase
from django.utils import translation

from home.utils import col_choices, list_humanize, row_choices


class ChoicesTests(SimpleTestCase):
    def test_row_and_col_choices_are_one_based_labels(self):
        self.assertEqual(
            list(row_choices()), [(0, "1"), (1, "2"), (2, "3"), (3, "4"), (4, "5")]
        )
        self.assertEqual(len(list(col_choices())), 6)
        self.assertEqual(list(col_choices())[-1], (5, "6"))


class ListHumanizeTests(SimpleTestCase):
    def setUp(self):
        translation.activate("en")
        self.addCleanup(translation.deactivate)

    def test_empty(self):
        self.assertEqual(list_humanize([]), "-")

    def test_single(self):
        self.assertEqual(list_humanize([7]), "7")

    def test_up_to_limit(self):
        self.assertEqual(list_humanize([1, 2]), "1 and 2")
        self.assertEqual(list_humanize([1, 2, 3, 4, 5]), "1, 2, 3, 4 and 5")

    def test_above_limit(self):
        self.assertEqual(list_humanize(range(1, 9)), "1, 2, 3, 4, 5 and +3")

    def test_custom_limit(self):
        self.assertEqual(list_humanize([1, 2, 3], limit=2), "1, 2 and +1")

    def test_accepts_generators(self):
        self.assertEqual(list_humanize(i for i in (1, 2)), "1 and 2")

    def test_portuguese(self):
        with translation.override("pt-br"):
            self.assertEqual(list_humanize([1, 2]), "1 e 2")
