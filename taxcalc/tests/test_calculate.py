import os
import json
from io import StringIO
import tempfile
import copy
import pytest
import numpy as np
import pandas as pd
from taxcalc import Policy, Records, Calculator, Behavior, Consumption
from taxcalc import create_distribution_table
from taxcalc import create_difference_table
from taxcalc import create_diagnostic_table


IRATES = {1991: 0.015, 1992: 0.020, 1993: 0.022, 1994: 0.020, 1995: 0.021,
          1996: 0.022, 1997: 0.023, 1998: 0.024, 1999: 0.024, 2000: 0.024,
          2001: 0.024, 2002: 0.024, 2003: 0.024, 2004: 0.024}

WRATES = {1991: 0.0276, 1992: 0.0419, 1993: 0.0465, 1994: 0.0498,
          1995: 0.0507, 1996: 0.0481, 1997: 0.0451, 1998: 0.0441,
          1999: 0.0437, 2000: 0.0435, 2001: 0.0430, 2002: 0.0429,
          2003: 0.0429, 2004: 0.0429}

RAWINPUTFILE_FUNITS = 4
RAWINPUTFILE_YEAR = 2015
RAWINPUTFILE_CONTENTS = (
    'RECID,MARS\n'
    '1,2\n'
    '2,1\n'
    '3,4\n'
    '4,6\n'
)


@pytest.yield_fixture
def rawinputfile():
    """
    Temporary input file that contains the minimum required input varaibles.
    """
    ifile = tempfile.NamedTemporaryFile(mode='a', delete=False)
    ifile.write(RAWINPUTFILE_CONTENTS)
    ifile.close()
    # must close and then yield for Windows platform
    yield ifile
    if os.path.isfile(ifile.name):
        try:
            os.remove(ifile.name)
        except OSError:
            pass  # sometimes we can't remove a generated temporary file


@pytest.yield_fixture
def policyfile():
    txt = """{"_almdep": {"value": [7150, 7250, 7400]},
             "_almsep": {"value": [40400, 41050]},
             "_rt5": {"value": [0.33 ]},
             "_rt7": {"value": [0.396]}}"""
    f = tempfile.NamedTemporaryFile(mode="a", delete=False)
    f.write(txt + "\n")
    f.close()
    # Must close and then yield for Windows platform
    yield f
    os.remove(f.name)


def test_make_Calculator(records_2009):
    parm = Policy(start_year=2014, num_years=9)
    assert parm.current_year == 2014
    recs = records_2009
    consump = Consumption()
    consump.update_consumption({2014: {'_MPC_e20400': [0.05]}})
    assert consump.current_year == 2013
    calc = Calculator(policy=parm, records=recs, consumption=consump)
    assert calc.current_year == 2014
    # test incorrect Calculator instantiation:
    with pytest.raises(ValueError):
        calc = Calculator(policy=None, records=recs)
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=None)
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=recs, behavior=list())
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=recs, growth=list())
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=recs, consumption=list())


def test_make_Calculator_deepcopy(records_2009):
    parm = Policy()
    calc1 = Calculator(policy=parm, records=records_2009)
    calc2 = copy.deepcopy(calc1)
    assert isinstance(calc2, Calculator)


def test_make_Calculator_with_policy_reform(records_2009):
    # create a Policy object and apply a policy reform
    policy2 = Policy()
    reform2 = {2013: {'_II_em': np.array([4000]), '_II_em_cpi': False,
                      '_STD_Aged': [[1600, 1300, 1300, 1600, 1600, 1300]],
                      "_STD_Aged_cpi": False}}
    policy2.implement_reform(reform2)
    # create a Calculator object using this policy-reform
    calc2 = Calculator(policy=policy2, records=records_2009)
    # check that Policy object embedded in Calculator object is correct
    assert calc2.current_year == 2013
    assert calc2.policy.II_em == 4000
    assert np.allclose(calc2.policy._II_em,
                       np.array([4000] * Policy.DEFAULT_NUM_YEARS))
    exp_STD_Aged = [[1600, 1300, 1300,
                     1600, 1600, 1300]] * Policy.DEFAULT_NUM_YEARS
    assert np.allclose(calc2.policy._STD_Aged,
                       np.array(exp_STD_Aged))
    assert np.allclose(calc2.policy.STD_Aged,
                       np.array([1600, 1300, 1300, 1600, 1600, 1300]))


def test_make_Calculator_with_multiyear_reform(records_2009):
    # create a Policy object and apply a policy reform
    policy3 = Policy()
    reform3 = {2015: {}}
    reform3[2015]['_STD_Aged'] = [[1600, 1300, 1600, 1300, 1600, 1300]]
    reform3[2015]['_II_em'] = [5000, 6000]  # reform values for 2015 and 2016
    reform3[2015]['_II_em_cpi'] = False
    policy3.implement_reform(reform3)
    # create a Calculator object using this policy-reform
    calc3 = Calculator(policy=policy3, records=records_2009)
    # check that Policy object embedded in Calculator object is correct
    assert calc3.current_year == 2013
    assert calc3.policy.II_em == 3900
    assert calc3.policy.num_years == Policy.DEFAULT_NUM_YEARS
    exp_II_em = [3900, 3950, 5000] + [6000] * (Policy.DEFAULT_NUM_YEARS - 3)
    assert np.allclose(calc3.policy._II_em,
                       np.array(exp_II_em))
    calc3.increment_year()
    calc3.increment_year()
    assert calc3.current_year == 2015
    assert np.allclose(calc3.policy.STD_Aged,
                       np.array([1600, 1300, 1600, 1300, 1600, 1300]))


def test_make_Calculator_with_reform_after_start_year(records_2009):
    # create Policy object using custom indexing rates
    irates = {2013: 0.01, 2014: 0.01, 2015: 0.02, 2016: 0.01, 2017: 0.03}
    parm = Policy(start_year=2013, num_years=len(irates),
                  inflation_rates=irates)
    # specify reform in 2015, which is two years after Policy start_year
    reform = {2015: {}, 2016: {}}
    reform[2015]['_STD_Aged'] = [[1600, 1300, 1600, 1300, 1600, 1300]]
    reform[2015]['_II_em'] = [5000]
    reform[2016]['_II_em'] = [6000]
    reform[2016]['_II_em_cpi'] = False
    parm.implement_reform(reform)
    calc = Calculator(policy=parm, records=records_2009)
    # compare actual and expected parameter values over all years
    assert np.allclose(calc.policy._STD_Aged,
                       np.array([[1500, 1200, 1200, 1500, 1500, 1200],
                                 [1550, 1200, 1200, 1550, 1550, 1200],
                                 [1600, 1300, 1600, 1300, 1600, 1300],
                                 [1632, 1326, 1632, 1326, 1632, 1326],
                                 [1648, 1339, 1648, 1339, 1648, 1339]]),
                       atol=0.5, rtol=0.0)  # handles rounding to dollars
    assert np.allclose(calc.policy._II_em,
                       np.array([3900, 3950, 5000, 6000, 6000]))
    # compare actual and expected values for 2015
    calc.increment_year()
    calc.increment_year()
    assert calc.current_year == 2015
    assert np.allclose(calc.policy.II_em, 5000)
    assert np.allclose(calc.policy.STD_Aged,
                       np.array([1600, 1300, 1600, 1300, 1600, 1300]))


def test_Calculator_advance_to_year(records_2009):
    policy = Policy()
    calc = Calculator(policy=policy, records=records_2009)
    calc.advance_to_year(2016)
    assert calc.current_year == 2016
    with pytest.raises(ValueError):
        calc.advance_to_year(2015)


def test_make_Calculator_user_mods_with_cpi_flags(policyfile, puf_1991):
    with open(policyfile.name) as pfile:
        policy = json.load(pfile)
    ppo = Policy(parameter_dict=policy, start_year=1991,
                 num_years=len(IRATES), inflation_rates=IRATES,
                 wage_growth_rates=WRATES)
    rec = Records(data=puf_1991, start_year=1991)
    calc = Calculator(policy=ppo, records=rec)
    user_mods = {1991: {"_almdep": [7150, 7250, 7400],
                        "_almdep_cpi": True,
                        "_almsep": [40400, 41050],
                        "_almsep_cpi": False,
                        "_rt5": [0.33],
                        "_rt7": [0.396]}}
    calc.policy.implement_reform(user_mods)
    # compare actual and expected values
    inf_rates = [IRATES[1991 + i] for i in range(0, Policy.DEFAULT_NUM_YEARS)]
    exp_almdep = Policy.expand_array(np.array([7150, 7250, 7400]),
                                     inflate=True,
                                     inflation_rates=inf_rates,
                                     num_years=Policy.DEFAULT_NUM_YEARS)
    act_almdep = getattr(calc.policy, '_almdep')
    assert np.allclose(act_almdep, exp_almdep)
    exp_almsep_values = [40400] + [41050] * (Policy.DEFAULT_NUM_YEARS - 1)
    exp_almsep = np.array(exp_almsep_values)
    act_almsep = getattr(calc.policy, '_almsep')
    assert np.allclose(act_almsep, exp_almsep)


def test_make_Calculator_raises_on_no_policy(records_2009):
    with pytest.raises(ValueError):
        calc = Calculator(records=records_2009)


def test_Calculator_attr_access_to_policy(records_2009):
    policy = Policy()
    calc = Calculator(policy=policy, records=records_2009)
    assert hasattr(calc.records, 'c01000')
    assert hasattr(calc.policy, '_AMT_Child_em')
    assert hasattr(calc, 'policy')


def test_Calculator_current_law_version(records_2009):
    policy = Policy()
    reform = {2013: {'_II_rt7': [0.45]}}
    policy.implement_reform(reform)
    calc = Calculator(policy=policy, records=records_2009)
    calc_clp = calc.current_law_version()
    assert isinstance(calc_clp, Calculator)
    assert calc.policy.II_rt6 == calc_clp.policy.II_rt6
    assert calc.policy.II_rt7 != calc_clp.policy.II_rt7


def test_Calculator_create_distribution_table(records_2009):
    policy = Policy()
    calc = Calculator(policy=policy, records=records_2009)
    calc.calc_all()
    dist_labels = ['Returns', 'AGI', 'Standard Deduction Filers',
                   'Standard Deduction', 'Itemizers',
                   'Itemized Deduction', 'Personal Exemption',
                   'Taxable Income', 'Regular Tax', 'AMTI', 'AMT Filers',
                   'AMT', 'Tax before Credits', 'Non-refundable Credits',
                   'Tax before Refundable Credits', 'Refundable Credits',
                   'Individual Income Tax Liabilities',
                   'Payroll Tax Liablities',
                   'Combined Payroll and Individual Income Tax Liabilities']
    dt1 = create_distribution_table(calc.records,
                                    groupby="weighted_deciles",
                                    result_type="weighted_sum")
    dt1.columns = dist_labels
    dt2 = create_distribution_table(calc.records,
                                    groupby="small_income_bins",
                                    result_type="weighted_avg")
    assert isinstance(dt1, pd.DataFrame)
    assert isinstance(dt2, pd.DataFrame)


def test_Calculator_mtr(records_2009):
    calc = Calculator(policy=Policy(), records=records_2009)
    recs_pre_e00200p = copy.deepcopy(calc.records.e00200p)
    (mtr_ptx, mtr_itx, mtr_combined) = calc.mtr(variable_str='e00200p',
                                                zero_out_calculated_vars=True)
    recs_post_e00200p = copy.deepcopy(calc.records.e00200p)
    assert np.allclose(recs_post_e00200p, recs_pre_e00200p)
    assert type(mtr_combined) == np.ndarray
    assert np.array_equal(mtr_combined, mtr_ptx) is False
    assert np.array_equal(mtr_ptx, mtr_itx) is False
    with pytest.raises(ValueError):
        (_, _, mtr_combined) = calc.mtr(variable_str='bad_income_type')
    (_, _, mtr_combined) = calc.mtr(variable_str='e00650',
                                    negative_finite_diff=True)
    assert type(mtr_combined) == np.ndarray
    (_, _, mtr_combined) = calc.mtr(variable_str='e00900p')
    assert type(mtr_combined) == np.ndarray
    (_, _, mtr_combined) = calc.mtr(variable_str='e01700')
    assert type(mtr_combined) == np.ndarray
    (_, _, mtr_combined) = calc.mtr(variable_str='e26270')
    assert type(mtr_combined) == np.ndarray


def test_Calculator_mtr_when_PT_rates_differ():
    reform = {2013: {'_II_rt1': [0.40],
                     '_II_rt2': [0.40],
                     '_II_rt3': [0.40],
                     '_II_rt4': [0.40],
                     '_II_rt5': [0.40],
                     '_II_rt6': [0.40],
                     '_II_rt7': [0.40],
                     '_PT_rt1': [0.30],
                     '_PT_rt2': [0.30],
                     '_PT_rt3': [0.30],
                     '_PT_rt4': [0.30],
                     '_PT_rt5': [0.30],
                     '_PT_rt6': [0.30],
                     '_PT_rt7': [0.30]}}
    funit = (
        u'RECID,MARS,FLPDYR,e00200,e00200p,e00900,e00900p,extraneous\n'
        u'1,    1,   2009,  200000,200000, 100000,100000, 9999999999\n'
    )
    pol1 = Policy()
    rec1 = Records(pd.read_csv(StringIO(funit)))
    calc1 = Calculator(policy=pol1, records=rec1)
    (_, mtr1, _) = calc1.mtr(variable_str='p23250')
    pol2 = Policy()
    pol2.implement_reform(reform)
    rec2 = Records(pd.read_csv(StringIO(funit)))
    calc2 = Calculator(policy=pol2, records=rec2)
    (_, mtr2, _) = calc2.mtr(variable_str='p23250')
    assert np.allclose(mtr1, mtr2, rtol=0.0, atol=1e-06)


def test_Calculator_create_difference_table(puf_1991, weights_1991):
    # create current-law Policy object and use to create Calculator calc1
    policy1 = Policy()
    puf1 = Records(data=puf_1991, weights=weights_1991, start_year=2009)
    calc1 = Calculator(policy=policy1, records=puf1)
    calc1.calc_all()
    # create policy-reform Policy object and use to create Calculator calc2
    policy2 = Policy()
    reform = {2013: {'_II_rt7': [0.45]}}
    policy2.implement_reform(reform)
    puf2 = Records(data=puf_1991, weights=weights_1991, start_year=2009)
    calc2 = Calculator(policy=policy2, records=puf2)
    # create difference table and check that it is a Pandas DataFrame
    dtable = create_difference_table(calc1.records, calc2.records,
                                     groupby="weighted_deciles")
    assert isinstance(dtable, pd.DataFrame)


def test_Calculator_create_diagnostic_table(records_2009):
    calc = Calculator(policy=Policy(), records=records_2009)
    calc.calc_all()
    adt = create_diagnostic_table(calc)
    assert isinstance(adt, pd.DataFrame)


def test_make_Calculator_increment_years_first(records_2009):
    # create Policy object with custom indexing rates and policy reform
    irates = {2013: 0.01, 2014: 0.01, 2015: 0.02, 2016: 0.01, 2017: 0.03}
    policy = Policy(start_year=2013, inflation_rates=irates,
                    num_years=len(irates))
    reform = {2015: {}, 2016: {}}
    reform[2015]['_STD_Aged'] = [[1600, 1300, 1600, 1300, 1600, 1300]]
    reform[2015]['_II_em'] = [5000]
    reform[2016]['_II_em'] = [6000]
    reform[2016]['_II_em_cpi'] = False
    policy.implement_reform(reform)
    # create Calculator object with Policy object as modified by reform
    calc = Calculator(policy=policy, records=records_2009)
    # compare expected policy parameter values with those embedded in calc
    exp_STD_Aged = np.array([[1500, 1200, 1200, 1500, 1500, 1200],
                             [1550, 1200, 1200, 1550, 1550, 1200],
                             [1600, 1300, 1600, 1300, 1600, 1300],
                             [1632, 1326, 1632, 1326, 1632, 1326],
                             [1648, 1339, 1648, 1339, 1648, 1339]])
    assert np.allclose(calc.policy._STD_Aged, exp_STD_Aged,
                       atol=0.5, rtol=0.0)  # handles rounding to dollars
    exp_II_em = np.array([3900, 3950, 5000, 6000, 6000])
    assert np.allclose(calc.policy._II_em, exp_II_em)


def test_ID_HC_vs_BS(puf_1991, weights_1991):
    """
    Test that complete haircut of itemized deductions produces same
    results as a 100% benefit surtax with no benefit deduction.
    """
    # specify complete-haircut reform policy and Calculator object
    hc_reform = {2013: {'_ID_Medical_hc': [1.0],
                        '_ID_StateLocalTax_hc': [1.0],
                        '_ID_RealEstate_hc': [1.0],
                        '_ID_Casualty_hc': [1.0],
                        '_ID_Miscellaneous_hc': [1.0],
                        '_ID_InterestPaid_hc': [1.0],
                        '_ID_Charity_hc': [1.0]}}
    hc_policy = Policy()
    hc_policy.implement_reform(hc_reform)
    hc_records = Records(data=puf_1991, weights=weights_1991, start_year=2009)
    hc_calc = Calculator(policy=hc_policy, records=hc_records)
    # specify benefit-surtax reform policy and Calculator object
    bs_reform = {2013: {'_ID_BenefitSurtax_crt': [0.0],
                        '_ID_BenefitSurtax_trt': [1.0]}}
    bs_policy = Policy()
    bs_policy.implement_reform(bs_reform)
    bs_records = Records(data=puf_1991, weights=weights_1991, start_year=2009)
    bs_calc = Calculator(policy=bs_policy, records=bs_records)
    # compare calculated tax results generated by the two reforms
    hc_calc.calc_all()
    bs_calc.calc_all()
    assert np.allclose(hc_calc.records._payrolltax,
                       bs_calc.records._payrolltax)
    assert np.allclose(hc_calc.records._iitax,
                       bs_calc.records._iitax)


def test_Calculator_using_nonstd_input(rawinputfile):
    # check Calculator handling of raw, non-standard input data with no aging
    policy = Policy()
    policy.set_year(RAWINPUTFILE_YEAR)  # set policy params to input data year
    nonpuf = Records(data=rawinputfile.name,
                     blowup_factors=None,  # keeps raw data unchanged
                     weights=None,
                     start_year=RAWINPUTFILE_YEAR)  # set raw input data year
    assert nonpuf.dim == RAWINPUTFILE_FUNITS
    calc = Calculator(policy=policy,
                      records=nonpuf,
                      sync_years=False)  # keeps raw data unchanged
    assert calc.current_year == RAWINPUTFILE_YEAR
    calc.calc_all()
    exp_iitax = np.zeros((nonpuf.dim,))
    assert np.allclose(nonpuf._iitax, exp_iitax)
    mtr_ptax, _, _ = calc.mtr(wrt_full_compensation=False)
    exp_mtr_ptax = np.zeros((nonpuf.dim,))
    exp_mtr_ptax.fill(0.153)
    assert np.allclose(mtr_ptax, exp_mtr_ptax)


REFORM_CONTENTS = """
// Example of a reform file suitable for the read_json_reform_file function.
// This JSON file can contain any number of trailing //-style comments, which
// will be removed before the contents are converted from JSON to a dictionary.
// Within each "policy", "behavior", and "growth" object, the
// primary keys are parameters and secondary keys are years.
// Both the primary and secondary key values must be enclosed in quotes (").
// Boolean variables are specified as true or false (no quotes; all lowercase).
{
  "policy": {
    "param_code": {
        "ALD_Investment_ec_base_code": "e00300 + e00650 + p23250"
    },
    "_AMT_brk1": // top of first AMT tax bracket
    {"2015": [200000],
     "2017": [300000]
    },
    "_EITC_c": // maximum EITC amount by number of qualifying kids (0,1,2,3+)
    {"2016": [[ 900, 5000,  8000,  9000]],
     "2019": [[1200, 7000, 10000, 12000]]
    },
    "_II_em": // personal exemption amount (see indexing changes below)
    {"2016": [6000],
     "2018": [7500],
     "2020": [9000]
    },
    "_II_em_cpi": // personal exemption amount indexing status
    {"2016": false, // values in future years are same as this year value
     "2018": true   // values in future years indexed with this year as base
    },
    "_SS_Earnings_c": // social security (OASDI) maximum taxable earnings
    {"2016": [300000],
     "2018": [500000],
     "2020": [700000]
    },
    "_AMT_em_cpi": // AMT exemption amount indexing status
    {"2017": false, // values in future years are same as this year value
     "2020": true   // values in future years indexed with this year as base
    }
  },
  "behavior": {
  },
  "growth": {
  }
}
"""


@pytest.yield_fixture
def reform_file():
    """
    Temporary reform file for read_json_reform_file function.
    """
    rfile = tempfile.NamedTemporaryFile(mode='a', delete=False)
    rfile.write(REFORM_CONTENTS)
    rfile.close()
    # must close and then yield for Windows platform
    yield rfile
    if os.path.isfile(rfile.name):
        try:
            os.remove(rfile.name)
        except OSError:
            pass  # sometimes we can't remove a generated temporary file


@pytest.mark.parametrize("set_year", [False, True])
def test_read_json_reform_file_and_implement_reform(reform_file, set_year):
    """
    Test reading and translation of reform file into a reform dictionary
    that is then used to call implement_reform method.
    NOTE: implement_reform called when policy.current_year == policy.start_year
    """
    reform, _, _ = Calculator.read_json_reform_file(reform_file.name)
    policy = Policy()
    if set_year:
        policy.set_year(2015)
    policy.implement_reform(reform)
    syr = policy.start_year
    amt_brk1 = policy._AMT_brk1
    assert amt_brk1[2015 - syr] == 200000
    assert amt_brk1[2016 - syr] > 200000
    assert amt_brk1[2017 - syr] == 300000
    assert amt_brk1[2018 - syr] > 300000
    ii_em = policy._II_em
    assert ii_em[2016 - syr] == 6000
    assert ii_em[2017 - syr] == 6000
    assert ii_em[2018 - syr] == 7500
    assert ii_em[2019 - syr] > 7500
    assert ii_em[2020 - syr] == 9000
    assert ii_em[2021 - syr] > 9000
    amt_em = policy._AMT_em
    assert amt_em[2016 - syr, 0] > amt_em[2015 - syr, 0]
    assert amt_em[2017 - syr, 0] > amt_em[2016 - syr, 0]
    assert amt_em[2018 - syr, 0] == amt_em[2017 - syr, 0]
    assert amt_em[2019 - syr, 0] == amt_em[2017 - syr, 0]
    assert amt_em[2020 - syr, 0] == amt_em[2017 - syr, 0]
    assert amt_em[2021 - syr, 0] > amt_em[2020 - syr, 0]
    assert amt_em[2022 - syr, 0] > amt_em[2021 - syr, 0]
    add4aged = policy._ID_Medical_frt_add4aged
    assert add4aged[2015 - syr] == -0.025
    assert add4aged[2016 - syr] == -0.025
    assert add4aged[2017 - syr] == 0.0
    assert add4aged[2022 - syr] == 0.0


@pytest.yield_fixture
def bad1reformfile():
    # specify JSON text for reform
    txt = """
    {
      "policy": { // example of incorrect JSON because 'x' must be "x"
        'x': {"2014": [4000]}
      },
      "behavior": {
      },
      "growth": {
      }
    }
    """
    f = tempfile.NamedTemporaryFile(mode='a', delete=False)
    f.write(txt + '\n')
    f.close()
    # Must close and then yield for Windows platform
    yield f
    os.remove(f.name)


@pytest.yield_fixture
def bad2reformfile():
    # specify JSON text for reform
    txt = """
    {
      "policy": {
        "_SS_Earnings_c": {"2018": [9e99]}
      },
      "behavior": {
      },
      "growthx": {
      }
    }
    """
    f = tempfile.NamedTemporaryFile(mode='a', delete=False)
    f.write(txt + '\n')
    f.close()
    # Must close and then yield for Windows platform
    yield f
    os.remove(f.name)


def test_read_bad_json_reform_file(bad1reformfile, bad2reformfile):
    with pytest.raises(ValueError):
        Calculator.read_json_reform_file(bad1reformfile.name)
    with pytest.raises(ValueError):
        Calculator.read_json_reform_file(bad2reformfile.name)


def test_convert_reform_dict():
    with pytest.raises(ValueError):
        rdict = Calculator.convert_reform_dict({2013: {'2013': [40000]}})
    with pytest.raises(ValueError):
        rdict = Calculator.convert_reform_dict({'_II_em': {2013: [40000]}})
    with pytest.raises(ValueError):
        rdict = Calculator.convert_reform_dict({4567: {2013: [40000]}})
    with pytest.raises(ValueError):
        rdict = Calculator.convert_reform_dict({'_II_em': 40000})
