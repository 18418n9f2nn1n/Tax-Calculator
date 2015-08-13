"""
OSPC Tax-Calculator policy Parameters class.
"""
# CODING-STYLE CHECKS:
# pep8 --ignore=E402 parameters.py
# pylint --disable=locally-disabled parameters.py

from .utils import expand_array
import os
import json


class Parameters(object):
    """
    Constructor for federal income tax policy parameters class.

    Parameters
    ----------
    parameter_dict: dictionary of PARAM:DESCRIPTION pairs
        dictionary of policy parameters; if None, default policy
        parameters are read from the params.json file.

    start_year: integer
        first calendar year for policy parameters.

    num_years: integer
        number of calendar years for which to specify policy parameter
        values beginning with start_year.

    inflation_rates: dictionary of YEAR:RATE pairs
        variable inflation rates used to project future policy parameter
        values; if None, then use default inflation rates specified
        here.

    Raises
    ------
    ValueError:
        if num_years is less than one.
        if len(inflation_rates) is not equal to num_years.
        if min(inflation_rates.keys()) is not equal to num_years.

    Returns
    -------
    class instance: Parameters
    """

    # default inflation rates by year
    __rates = {2013: 0.015, 2014: 0.020, 2015: 0.022, 2016: 0.020, 2017: 0.021,
               2018: 0.022, 2019: 0.023, 2020: 0.024, 2021: 0.024, 2022: 0.024,
               2023: 0.024, 2024: 0.024}

    @classmethod
    def default_inflation_rate(cls, calyear):
        """
        Return default inflation rate for specified calendar year.

        Parameters
        ----------
        calyear: integer
            calendar year (for example, 2013).

        Returns
        -------
        default inflation rate: float
            decimal (not percentage) annual inflation rate for calyear.
        """
        return cls.__rates[calyear]

    @classmethod
    def default_inflation_rates(cls):
        """
        Return complete default inflation rate dictionary.

        Parameters
        ----------
        none

        Returns
        -------
        default inflation rates: dict
            decimal (not percentage) annual inflation rate by calyear.
        """
        return cls.__rates

    JSON_FILE_NAME = 'params.json'
    JSON_START_YEAR = 2013

    def __init__(self, parameter_dict=None,
                 start_year=JSON_START_YEAR,
                 num_years=12,
                 inflation_rates=None):
        """
        Parameters class constructor.
        """
        if parameter_dict:
            self._vals = parameter_dict
        else:  # if None, read current-law parameters
            self._vals = self._params_dict_from_json_file()

        if num_years < 1:
            raise ValueError('num_years < 1')

        if inflation_rates:
            if len(inflation_rates) != num_years:
                raise ValueError('len(inflation_rates) != num_years')
            if min(list(inflation_rates.keys())) != start_year:
                raise ValueError('min(inflation_rates.keys()) != start_year')
            self._inflation_rates = [inflation_rates[start_year + i]
                                     for i in range(0, num_years)]
        else:  # if None, read default rates
            self._inflation_rates = [self.__rates[start_year + i]
                                     for i in range(0, num_years)]

        self._current_year = start_year
        self._start_year = start_year
        self._num_years = num_years
        self._end_year = start_year + num_years - 1

        # extend current-law parameter values into future with _inflation_rates
        for name, data in self._vals.items():
            cpi_inflated = data.get('cpi_inflated', False)
            values = data['value']
            setattr(self, name,
                    expand_array(values, inflate=cpi_inflated,
                                 inflation_rates=self._inflation_rates,
                                 num_years=self._num_years))
        self.set_year(self._start_year)

    def implement_reform(self, reform):
        """
        Implement multi-year parameters reform and set current_year=start_year.

        Parameters
        ----------
        reform: dictionary of YEAR:MODS pairs
            see Notes to _update function below for MODS structure.

        Raises
        ------
        ValueError:
            if maximum YEAR in the YEAR:MODS pairs is greater than end_year.

        Returns
        -------
        nothing: void

        Notes
        -----
        Given a reform_dict, typical usage of the Parameters class is
        as follows:

        ppo = Parameters().implement_reform(reform_dict)

        In the above statement, the Parameters() call instantiates a
        policy parameters object (ppo) containing current-law policy
        parameters, and the implement_reform(reform_dict) call applies
        the (possibly multi-year) reform specified in reform_dict and
        after doing that sets the current_year to start_year.
        """
        if self.current_year != self.start_year:
            self.set_year(self.start_year)
        if not reform:
            return  # no reform to implement
        reform_years = sorted(list(reform.keys()))
        last_reform_year = max(reform_years)
        if last_reform_year > self.end_year:
            msg = 'reform provision in year={} > end_year={}'
            ValueError(msg.format(last_reform_year, self.end_year))
        for year in reform_years:
            if year != self.start_year:
                self.set_year(year)
            self._update({year: reform[year]})
        self.set_year(self.start_year)

    @property
    def current_year(self):
        """
        Current policy parameter year property.
        """
        return self._current_year

    @property
    def start_year(self):
        """
        First policy parameter year property.
        """
        return self._start_year

    @property
    def num_years(self):
        """
        Number of policy parameter years property.
        """
        return self._num_years

    @property
    def end_year(self):
        """
        Last policy parameter year property.
        """
        return self._end_year

    def set_year(self, year):
        """
        Set policy parameters to values for specified calendar year.

        Parameters
        ----------
        year: int
            calendar year for which to current_year and parameter values

        Raises
        ------
        ValueError:
            if year is not in [start_year, end_year] range.

        Returns
        -------
        nothing: void

        Notes
        -----
        To increment the current year, use the following statement:

        ppo.set_year(ppo.current_year + 1)

        where ppo is a policy Parameters object.
        """
        if year < self.start_year or year > self.end_year:
            msg = 'year passed to set_year() must be in [{},{}] range.'
            raise ValueError(msg.format(self.start_year, self.end_year))
        self._current_year = year
        year_zero_indexed = year - self._start_year
        for name in self._vals:
            arr = getattr(self, name)
            setattr(self, name[1:], arr[year_zero_indexed])

    @classmethod
    def default_data(cls, metadata=False, first_value_year=None):
        """
        Return current-law policy data read from params.json file.

        Parameters
        ----------
        metadata: boolean

        first_value_year: int

        Raises
        ------
        ValueError:
            if first_value_year is not in [start_year, end_year] range.

        Returns
        -------
        params: dictionary of params.json information
        """
        params = cls._params_dict_from_json_file()

        if first_value_year:  # if first_value_year is specified
            f_v_year_string = '{}'.format(first_value_year)
            for name,pdv in params.items():  # pdv = parameter dictionary value
                s_year = pdv.get('start_year', Parameters.JSON_START_YEAR)
                assert isinstance(s_year, int)
                if first_value_year < s_year:
                    msg = "first_value_year={} < start_year={} for {}"
                    raise ValueError(msg.format(first_value_year,
                                                s_year, name))
                # set the new start year:
                pdv['start_year'] = first_value_year
                # work with the values
                vals = pdv['value']
                last_year_for_data = s_year + len(vals) - 1
                if last_year_for_data < first_value_year:
                    if pdv['row_label']:
                        pdv['row_label'] = [f_v_year_string]
                    # need to produce new values
                    new_val = vals[-1]
                    if pdv['cpi_inflated'] is True:
                        for cyr in range(last_year_for_data, first_value_year):
                            irate = Parameters.default_inflation_rate(cyr)
                            ifactor = 1.0 + irate
                        if isinstance(new_val, list):
                            new_val = [x * ifactor for x in new_val]
                        else:
                            new_val *= ifactor
                    # set the new values
                    pdv['value'] = [new_val]
                else:
                    # get rid of [s_year, ..., first_value_year-1] values
                    years_to_chop = first_value_year - s_year
                    if pdv['row_label']:
                        pdv['row_label'] = pdv['row_label'][years_to_chop:]
                    pdv['value'] = pdv['value'][years_to_chop:]

        if metadata:
            return params
        else:
            return {key: val['value'] for key, val in params.items()}

    # ----- begin private methods of Parameters class -----

    @classmethod
    def _params_dict_from_json_file(cls):
        """
        Read params.json file and return complete params dictionary.

        Parameters
        ----------
        nothing: void

        Returns
        -------
        params: dictionary
            containing complete contents of params.json file.
        """
        params_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                   Parameters.JSON_FILE_NAME)
        if os.path.exists(params_path):
            with open(params_path) as pfile:
                params = json.load(pfile)
        else:
            from pkg_resources import resource_stream, Requirement
            path_in_egg = os.path.join('taxcalc', Parameters.JSON_FILE_NAME)
            buf = resource_stream(Requirement.parse('taxcalc'), path_in_egg)
            as_bytes = buf.read()
            as_string = as_bytes.decode("utf-8")
            params = json.loads(as_string)
        return params

    def _update(self, year_mods):
        """
        Apply year_mods policy-parameter-reform dictionary to parameters.

        Parameters
        ----------
        year_mods: dictionary of a single YEAR:MODS pair
            see Notes below for details on dictionary structure.

        Raises
        ------
        ValueError:
            if year_mods is not a dictionary of the expected structure.

        Returns
        -------
        nothing: void

        Notes
        -----
        This method implements a policy reform, the provisions of
        which are specified in the year_mods dictionary, that changes
        the values of some policy parameters in this Parameters
        object.  This year_modes dictionary contains exactly one
        YEAR:MODS pair, where the integer YEAR key indicates the
        calendar year for which the reform provisions in the MODS
        dictionary are implemented.  The MODS dictionary contains
        PARAM:VALUE pairs in which the PARAM is a string specifying
        the policy parameter (as used in the params.json default
        parameter file) and the VALUE is a Python list of post-reform
        values for that PARAM in that YEAR.  Beginning in the year
        following the implementation of a reform provision, the
        parameter whose value has been changed by the reform continues
        to be inflation indexed or not be inflation indexed according
        to that parameter's cpi_inflated value in the params.json
        file.  But a reform can change the indexing status of a
        parameter by including in the MODS dictionary a term that is a
        PARAM_cpi:BOOLEAN pair specifying the post-reform indexing
        status of the parameter.

        So, for example, to raise the OASDI (i.e., Old-Age, Survivors,
        and Disability Insurance) maximum taxable earnings beginning
        in 2018 to $500,000 and to continue indexing it in subsequent
        years as in current-law policy, the YEAR:MODS dictionary would
        be as follows:
        {2018: {"_SS_Earnings_c":[500000]}}.

        But to raise the maximum taxable earnings in 2018 to $500,000
        without any indexing in subsequent years, the YEAR:MODS
        dictionary would be as follows:
        {2018: {"_SS_Earnings_c":[500000], "_SS_Earnings_c_cpi":False}}.

        And to raise in 2019 the starting AGI for EITC phaseout for
        married filing jointly filing status (which is a two-dimensional
        policy parameter that varies by the number of children from zero
        to three or more and is inflation indexed), the YEAR:MODS dictionary
        would be as follows:
        {2019: {"_EITC_ps_MarriedJ":[[8000, 8500, 9000, 9500]]}}.
        Notice the pair of double square brackets around the four values
        for 2019.  The one-dimensional parameters above require only a pair
        of single square brackets.
        """
        # check YEAR value in the single YEAR:MODS dictionary parameter
        if not isinstance(year_mods, dict):
            msg = 'year_mods is not a dictionary'
            raise ValueError(msg)
        if len(year_mods.keys()) != 1:
            msg = 'year_mods dictionary must contain a single YEAR:MODS pair'
            raise ValueError(msg)
        year = list(year_mods.keys())[0]
        if not isinstance(year, int):
            msg = 'YEAR in the YEAR:MODS pair in year_mods is not an integer'
            raise ValueError(msg)
        if year != self.current_year:
            msg = 'YEAR={} in year_mods is not equal to current_year={}'
            raise ValueError(msg.format(year, self.current_year))

        # implement reform provisions included in the single YEAR:MODS pair
        num_years_to_expand = (self.start_year + self.num_years) - year
        inf_rates = [self._inflation_rates[(year - self.start_year) + i]
                     for i in range(0, num_years_to_expand)]
        paramvals = self._vals
        for name, values in year_mods[year].items():
            # determine inflation indexing status of parameter with name
            if name.endswith('_cpi'):
                continue
            if name in paramvals:
                default_cpi = paramvals[name].get('cpi_inflated', False)
            else:
                default_cpi = False
            cpi_inflated = year_mods[year].get(name + '_cpi', default_cpi)
            # set post-reform values of parameter with name
            nval = expand_array(values,
                                inflate=cpi_inflated,
                                inflation_rates=inf_rates,
                                num_years=num_years_to_expand)
            cval = getattr(self, name)
            cval[(self.current_year - self.start_year):] = nval
            setattr(self, name, cval)
        self.set_year(self._current_year)

    # TODO: eventually remove the following variable that
    #       is used only in the global default_data() function below
    PARAMS_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                               JSON_FILE_NAME)

# end Parameters class


def default_data(metadata=False, start_year=None):
    """
    Retrieve current-law policy parameters from params.json file.
    """
    # pylint: disable=too-many-locals,too-many-branches

    if not os.path.exists(Parameters.PARAMS_PATH):
        from pkg_resources import resource_stream, Requirement
        path_in_egg = os.path.join("taxcalc", Parameters.JSON_FILE_NAME)
        buf = resource_stream(Requirement.parse("taxcalc"), path_in_egg)
        _bytes = buf.read()
        as_string = _bytes.decode("utf-8")
        params = json.loads(as_string)
    else:
        with open(Parameters.PARAMS_PATH) as pfile:
            params = json.load(pfile)

    if start_year:
        for pdv in params.values():  # pdv = parameter dictionary value
            first_year = pdv.get('start_year', Parameters.JSON_START_YEAR)
            assert isinstance(first_year, int)

            if start_year < first_year:
                msg = "Can't set a start year of {0}, because it is before {1}"
                raise ValueError(msg.format(start_year, first_year))

            # set the new start year:
            pdv['start_year'] = start_year

            # work with the values
            vals = pdv['value']
            last_year_for_data = first_year + len(vals) - 1

            if last_year_for_data < start_year:
                if pdv['row_label']:
                    pdv['row_label'] = ["2015"]
                # need to produce new values
                new_val = vals[-1]
                if pdv['cpi_inflated'] is True:
                    for cyr in range(last_year_for_data, start_year):
                        ifactor = 1.0 + Parameters.default_inflation_rate(cyr)
                        if isinstance(new_val, list):
                            new_val = [x * ifactor for x in new_val]
                        else:
                            new_val *= ifactor
                # set the new values
                pdv['value'] = [new_val]

            else:
                # need to get rid of [first_year, ..., start_year-1] values
                years_to_chop = start_year - first_year
                if pdv['row_label']:
                    pdv['row_label'] = pdv['row_label'][years_to_chop:]
                pdv['value'] = pdv['value'][years_to_chop:]

    if metadata:
        return params
    else:
        return {key: val['value'] for key, val in params.items()}
