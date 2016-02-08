import datetime
from mock import Mock

import pandas.util.testing as tm
import pandas as pd

from pandas_finance import Equity, Option, OptionChain


class TestEquity(tm.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aapl = Equity('AAPL')
        cls.date = datetime.date(2013, 1, 25)

    def test_equity_price(self):
        self.assertAlmostEqual(self.aapl.close[self.date], 439.88, 2)

    def test_historical_vol(self):
        vol = self.aapl.hist_vol(30, end_date=self.date)
        self.assertAlmostEqual(vol, 0.484, 3)

    def test_options(self):
        self.assertIsInstance(self.aapl.options, OptionChain)

    def test_annual_dividend(self):
        self.assertEqual(self.aapl.annual_dividend, 0.52 * 4)

    def test_dividends(self):
        self.assertEqual(self.aapl.dividends[datetime.date(2015, 11, 5)], 0.52)

    def test_price(self):
        self.assertIsInstance(self.aapl.price, float)

    def test_sector(self):
        self.assertEqual(self.aapl.sector, 'Consumer Goods')

    def test_employees(self):
        self.assertGreater(self.aapl.employees, 100000)

    def test_industry(self):
        self.assertEqual(self.aapl.industry, 'Electronic Equipment')

    def test_name(self):
        self.assertEqual(self.aapl.name, 'Apple Inc.')


class TestOptionChain(tm.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aapl = Equity('AAPL')
        cls.options = OptionChain(cls.aapl)

    def test_options(self):
        self.assertIsInstance(self.options.all_data, pd.DataFrame)

    def test_calls(self):
        self.assertIsInstance(self.options.calls, pd.DataFrame)
        self.assertTrue((self.options.calls.index.get_level_values('Type') == 'call').all())

    def test_puts(self):
        self.assertIsInstance(self.options.puts, pd.DataFrame)
        self.assertTrue((self.options.puts.index.get_level_values('Type') == 'put').all())

    def test_near_calls(self):
        self.assertIsInstance(self.options.near_calls, pd.DataFrame)
        self.assertTrue((self.options.near_calls.index.get_level_values('Type') == 'call').all())

    def test_near_puts(self):
        self.assertIsInstance(self.options.near_puts, pd.DataFrame)
        self.assertTrue((self.options.near_puts.index.get_level_values('Type') == 'put').all())

    # def test_to_options(self):
    #     self.assertIsInstance(self.options.near_puts, pd.DataFrame)
    #     self.assertTrue((self.options.near_puts.index.get_level_values('Type')=='put').all())


class TestCallOption(tm.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aapl = Mock(Equity)
        cls.aapl.price = 115
        cls.aapl.annual_dividend = 0.52*4
        cls.aapl._session = None
        cls.aapl.ticker = 'AAPL'
        cls.aapl.hist_vol = Mock(return_value = 0.26)

        cls.options = OptionChain(cls.aapl)
        cls.option = Option(
                underlying=cls.aapl,
                expiry = datetime.date(2016,12,31),
                strike = 115,
                type = 'call',
                price = 11.04,
                interest_rate = 0.005,
                valuation_date = datetime.date(2015,12,31)
                )

    def test_call_option_value(self):
        self.assertAlmostEqual(self.option.value, 11.04, 2)

    def test_implied_volatility(self):
        self.assertAlmostEqual(self.option.implied_volatility, 0.26, 2)

    def test_gamma(self):
        self.assertAlmostEqual(self.option.gamma, 0.013, 3)

    def test_theta(self):
        self.assertAlmostEqual(self.option.theta, -0.014, 3)

    def test_vega(self):
        self.assertAlmostEqual(self.option.vega, 0.45, 2)

    def test_rho(self):
        self.assertAlmostEqual(self.option.rho, 0.49, 2)

    def test_hist_vol(self):
        self.assertAlmostEqual(self.option.historical_volatility, 0.26, 2)

    def test_raise(self):
        self.assertRaises(
            Option(
                underlying=self.aapl,
                expiry = datetime.date(2016,12,31),
                strike = 115,
                type = 'notarealoptiontype',
                price = 11.04,
                interest_rate = 0.005,
                valuation_date = datetime.date(2015,12,31)
                ),
            ValueError)
