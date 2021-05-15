import unittest
from utils import metricify


class TestMetricify(unittest.TestCase):

    def test_postive(self):
        self.assertEqual('0', metricify(0))
        self.assertEqual('1', metricify(1))
        self.assertEqual('999', metricify(999))
        self.assertEqual('9999', metricify(9999))
        self.assertEqual('10000', metricify(10000))
        self.assertEqual('99999', metricify(99999))
        self.assertEqual('100K', metricify(100000))
        self.assertEqual('9999K', metricify(9999999))
        self.assertEqual('10M', metricify(10000000))
        self.assertEqual('9999M', metricify(9999999999))
        self.assertEqual('10G', metricify(10000000000))
        self.assertEqual('9999G', metricify(9999999999999))

    def test_negative(self):
        self.assertEqual('-1', metricify(-1))
        self.assertEqual('-999', metricify(-999))
        self.assertEqual('-9999', metricify(-9999))
        self.assertEqual('-10K', metricify(-10000))
        self.assertEqual('-999K', metricify(-999999))
        self.assertEqual('-1M', metricify(-1000000))
        self.assertEqual('-1.1M', metricify(-1100000))
        self.assertEqual('-9.9M', metricify(-9900000))
        self.assertEqual('-10M', metricify(-10000000))
        self.assertEqual('-999M', metricify(-999999999))
        self.assertEqual('-1G', metricify(-1000000000))
        self.assertEqual('-1.1G', metricify(-1100000000))
        self.assertEqual('-10G', metricify(-10000000000))
        self.assertEqual('-999G', metricify(-999999999999))

if __name__ == '__main__':
    unittest.main()