import datetime
import math

import pandas as pd
import mibian
import requests_cache
import pandas_datareader.data as pdr
import requests_cache
from bs4 import BeautifulSoup

TRADING_DAYS = 252
CACHE_HRS = 1
START_DATE = datetime.date(1990, 1, 1)


class Equity(object):
    def __init__(self, ticker, session=None):
        self.ticker = ticker

        if session:
            self._session = session
        else:
            self._session = self._get_session()

        self.PROFILE_URL = 'http://finance.yahoo.com/q/pr?s={ticker}+Profile'.format(ticker=self.ticker)

    def _get_session(self):
        return requests_cache.CachedSession(cache_name='pf-cache', backend='sqlite',
                                            expire_after=datetime.timedelta(hours=CACHE_HRS))

    @property
    def options(self):
        return OptionChain(self)

    @property
    def close(self):
        """Returns pandas series of closing price"""
        return self.trading_data['Close']

    @property
    def adj_close(self):
        """Returns pandas series of closing price"""
        return self.trading_data['Adj Close']

    @property
    def returns(self):
        return self.adj_close.pct_change()

    @property
    def trading_data(self):
        return pdr.DataReader(self.ticker, 'yahoo', session=self._session, start=START_DATE)

    @property
    def dividends(self):
        actions = pdr.DataReader(self.ticker, 'yahoo-actions', session=self._session)
        dividends = actions[actions['action'] == 'DIVIDEND']
        dividends = dividends['value']
        dividends.name = 'Dividends'
        return dividends.sort_index()

    @property
    def annual_dividend(self):
        time_between = self.dividends.index[-1] - self.dividends.index[-2]
        times_per_year = round(365 / time_between.days, 0)
        return times_per_year * self.dividends.values[-1]

    @property
    def dividend_yield(self):
        return self.annual_dividend / self.price

    @property
    def price(self):
        return pdr.get_quote_yahoo(self.ticker)['last'][0]

    def hist_vol(self, days, end_date=None):
        days = int(days)
        if end_date:
            data = self.returns[:end_date]
        else:
            data = self.returns
        data = data.iloc[-days:]
        return data.std() * math.sqrt(TRADING_DAYS)

    def rolling_hist_vol(self, days, end_date=None):
        if end_date:
            data = self.returns[:end_date]
        else:
            data = self.returns
        return pd.rolling_std(data, window=days) * math.sqrt(TRADING_DAYS)

    @property
    def profile(self):
        page = self._session.get(self.PROFILE_URL).content
        profile = pd.read_html(page)[5]
        profile = profile.set_index(0)
        profile.index.name = ""
        profile = profile.iloc[:, 0]
        profile.name = ""
        profile.index = [name.strip(':') for name in profile.index]
        return profile

    @property
    def sector(self):
        return self.profile['Sector']

    @property
    def industry(self):
        return self.profile['Industry']

    @property
    def employees(self):
        return int(self.profile['Full Time Employees'].replace(',', ''))

    @property
    def name(self):
        page = self._session.get(self.PROFILE_URL).content
        soup = BeautifulSoup(page)
        return soup.find_all(class_='title')[0].text.split('-')[0].strip()


class Option(object):

    _CALL_TYPES = ['c','call']
    _PUT_TYPES = ['p','put']
    _VALID_TYPES = _CALL_TYPES + _PUT_TYPES

    def __init__(self, underlying, expiry, strike, type, price=None, volatility=None,
            valuation_date=None, interest_rate=None):

        self.underlying = underlying
        self.expiry = expiry
        self.strike = strike
        self.type = type
        self.price = price

        self._validate_type()

        if valuation_date:
            self.valuation_date = valuation_date
        else:
            self.valuation_date = datetime.date.today()

        if interest_rate:
            self.interest_rate = interest_rate
        else:
            # TODO: get appropriate interest rate
            # TODO: Document that interest rate should be in decimal form
            self.interest_rate = 0.005

        if volatility:
            # TODO: Document that volatility should be in decimal form
            self.volatility = volatility
        else:
            # Use historical volatility for same time period if none given
            # TODO: Business days vs trading days issue here (hist_vol is
            # trading days)
            self.volatility = self.historical_volatility

    @property
    def _me(self):
        return mibian.Me([
            self.underlying.price,
            self.strike,
            self.interest_rate * 100,
            self.underlying.annual_dividend,
            self.days_to_expiration],
            self.volatility *100,
            )

    @property
    def _me_implied_vol(self):
        return mibian.Me([
            self.underlying.price,
            self.strike,
            self.interest_rate * 100,
            self.underlying.annual_dividend,
            self.days_to_expiration],
            self.volatility *100,
            self._call_price,
            self._put_price
            )

    @property
    def _me_at_implied_vol(self):
        return mibian.Me([
            self.underlying.price,
            self.strike,
            self.interest_rate * 100,
            self.underlying.annual_dividend,
            self.days_to_expiration],
            self.implied_volatility *100,
            )

    def _validate_type(self):
        if self.type.lower() not in self._VALID_TYPES:
            raise ValueError('{type} not a valid option type.  Valid types are {types}'.format(
                type=self.type, types = ','.join(self._VALID_TYPES)))

    @property
    def _is_call(self):
        return self.type.lower() in self._CALL_TYPES

    @property
    def _is_put(self):
        return self.type.lower() in self._PUT_TYPES

    @property
    def _call_price(self):
        if self._is_call:
            return self.price
        else:
            return None

    @property
    def _put_price(self):
        if self._is_put:
            return self.price
        else:
            return None

    @property
    def value(self):
        if self._is_call:
            return self._me.callPrice
        elif self._is_put:
            return self._me.putPrice

    @property
    def days_to_expiration(self):
        return (self.expiry - self.valuation_date).days

    @property
    def delta(self):
        if self._is_call:
            return self._me.callDelta
        elif self._is_put:
            return self._me.putDelta

    @property
    def vega(self):
        return self._me.vega

    @property
    def theta(self):
        if self._is_call:
            return self._me.callTheta
        elif self._is_put:
            return self._me.putTheta

    @property
    def rho(self):
        if self._is_call:
            return self._me.callRho
        elif self._is_put:
            return self._me.putRho

    @property
    def gamma(self):
        return self._me.gamma

    @property
    def implied_volatility(self):
        if not self.price:
            raise ValueError('Provide an option price in order to calculate Implied Volatility')
        return self._me_implied_vol.impliedVolatility/100

    @property
    def historical_volatility(self):
        return self.underlying.hist_vol(self.days_to_expiration)


class OptionChain(object):
    def __init__(self, underlying):
        self.underlying = underlying
        self._session = self.underlying._session
        self._pdr = pdr.Options(self.underlying.ticker, 'yahoo', session=self._session)

    @property
    def all_data(self):
        return self._pdr.get_all_data()

    @property
    def calls(self):
        data = self.all_data
        mask = data.index.get_level_values('Type') == 'call'
        return data[mask]

    @property
    def puts(self):
        data = self.all_data
        mask = data.index.get_level_values('Type') == 'put'
        return data[mask]

    @property
    def near_puts(self):
        return self._pdr.chop_data(self.puts, 5, self.underlying.price)

    @property
    def near_calls(self):
        return self._pdr.chop_data(self.calls, 5, self.underlying.price)

    def __getattr__(self, key):
        if hasattr(self._pdr, key):
            return getattr(self._pdr, key)

    def __dir__(self):
        return sorted(set((dir(type(self)) + list(self.__dict__) +
                           dir(self._pdr))))
