"""
Tests for Tax-Calculator functions.py logic.
"""
# CODING-STYLE CHECKS:
# pep8 --ignore=E402 test_functions.py
# pylint --disable=locally-disabled test_functions.py
# (when importing numpy, add "--extension-pkg-whitelist=numpy" pylint option)

import os
import sys
import re
from taxcalc import IncomeTaxIO  # pylint: disable=import-error
from io import StringIO
import pandas as pd


def test_function_args_usage():
    """
    Checks each function argument in functions.py for use in its function body.
    """
    cur_path = os.path.abspath(os.path.dirname(__file__))
    funcfilename = os.path.join(cur_path, '..', 'functions.py')
    with open(funcfilename, 'r') as funcfile:
        fcontent = funcfile.read()
    fcontent = re.sub('#.*', '', fcontent)  # remove all '#...' comments
    fcontent = re.sub('\n', ' ', fcontent)  # replace EOL character with space
    funcs = fcontent.split('def ')  # list of function text
    for func in funcs[1:]:  # skip first item in list, which is imports, etc.
        fcode = func.split('return ')[0]  # fcode is between def and return
        match = re.search(r'^(.+?)\((.*?)\):(.*)$', fcode)
        if match is None:
            msg = ('Could not find function name, arguments, '
                   'and code portions in the following text:')
            line = '====================================================='
            sys.stdout.write('{}\n{}\n{}\n{}\n'.format(msg, line, fcode, line))
            assert False
        else:
            fname = match.group(1)
            fargs = match.group(2).split(',')  # list of function arguments
            fbody = match.group(3)
        for farg in fargs:
            arg = farg.strip()
            if fbody.find(arg) < 0:
                msg = '{} function argument {} never used\n'.format(fname, arg)
                sys.stdout.write(msg)
                assert 'arg' == 'UNUSED'


def test_1():
    """
    Test calculation of AGI adjustment for half of Self-Employment Tax,
    which is the FICA payroll tax on self-employment income.
    """
    agi_ovar_num = 10
    # specify a reform that simplifies the hand calculations
    mte = 100000  # lower than current-law to simplify hand calculations
    ssr = 0.124  # current law OASDI ee+er payroll tax rate
    mrr = 0.029  # current law HI ee+er payroll tax rate
    reform = {
        2015: {
            '_SS_Earnings_c': [mte],
            '_FICA_ss_trt': [ssr],
            '_FICA_mc_trt': [mrr]
        }
    }
    funit = (
        u'RECID,MARS,e00200,e00200p,e00900,e00900p,e00900s\n'
        u'1,    2,   200000, 200000,200000,      0, 200000\n'
        u'2,    1,   100000, 100000,200000, 200000,      0\n'
    )
    # ==== Filing unit with RECID=1:
    # The expected AGI for this filing unit is $400,000 minus half of
    # the spouse's Self-Employment Tax (SET), which represents the
    # "employer share" of the SET.  The spouse pays OASDI SET on only
    # $100,000 of self-employment income, which implies a tax of
    # $12,400.  The spouse also pays HI SET on 0.9235 * 200000 * 0.029,
    # which implies a tax of $5,356.30.  So, the spouse's total SET is
    # the sum of the two, which equals $17,756.30.
    # The SET AGI adjustment is one-half of that amount, which is $8,878.15.
    # So, filing unit's AGI is $400,000 less this, which is $391,121.85.
    expected_agi_1 = '391121.85'
    # ==== Filing unit with RECID=2:
    # The expected AGI for this filing unit is $300,000 minus half of
    # the individual's Self-Employment Tax (SET), which represents the
    # "employer share" of the SET.  The individual pays no OASDI SET
    # because wage and salary income was already at the MTE.  So, the
    # only SET the individual pays is for HI, which is a tax equal to
    # 0.9235 * 200000 * 0.029, or $5,356.30.  One half of that amount
    # is $2,678.15, which implies the AGI is $297,321.85.
    expected_agi_2 = '297321.85'
    input_dataframe = pd.read_csv(StringIO(funit))
    inctax = IncomeTaxIO(input_data=input_dataframe,
                         tax_year=2015,
                         policy_reform=reform,
                         blowup_input_data=False)
    output = inctax.calculate()
    output_lines_list = output.split('\n')
    output_vars_list = output_lines_list[0].split()
    agi = output_vars_list[agi_ovar_num - 1]
    assert agi == expected_agi_1
    output_vars_list = output_lines_list[1].split()
    agi = output_vars_list[agi_ovar_num - 1]
    assert agi == expected_agi_2


import pytest
@pytest.mark.one
def test_2():
    """
    Test calculation of Additional Child Tax Credit when at least one of
    taxpayer and spouse have wage-and-salary income above the FICA maximum
    taxable earnings.
    """
    ctc_ovar_num = 22
    actc_ovar_num = 23
    # specify a reform that simplifies the hand calculations
    actc_thd = 35000
    mte = 53000
    reform = {
        2015: {
            '_ACTC_Income_thd': [actc_thd],
            '_SS_Earnings_c': [mte],
        }
    }
    funit = (
        u'RECID,MARS,XTOT,n24,e00200,e00200p\n'
        u'1,    2,   7,     7, 60000,  60000\n'
    )
    expected_ctc = '2500.00'
    expected_actc = '9.99'  # WHAT IS CORRECT AMOUNT?
    input_dataframe = pd.read_csv(StringIO(funit))
    inctax = IncomeTaxIO(input_data=input_dataframe,
                         tax_year=2015,
                         policy_reform=reform,
                         blowup_input_data=False)
    output = inctax.calculate()
    output_vars_list = output.split()
    ctc = output_vars_list[ctc_ovar_num - 1]
    actc = output_vars_list[actc_ovar_num - 1]
    print ctc, actc  # TODO remove debugging prints on this line and below
    print "c82925:", inctax._calc.records.c82925
    print "c82935:", inctax._calc.records.c82935
    print "c82880:", inctax._calc.records.c82880
    print "c82885:", inctax._calc.records.c82885
    print "c82900>", inctax._calc.records.c82885*0.15
    print "c82905:", inctax._calc.records.c82905
    print "c82910:", inctax._calc.records.c82910
    print "c82920:", inctax._calc.records.c82920
    print "c82937:", inctax._calc.records.c82937
    # assert ctc == expected_ctc
    # assert actc == expected_actc
    """
    WITH BAD FICA:
    1987.50 4054.50
    c82925: [ 7000.]
    c82935: [ 5012.5]
    c82880: [ 60000.]
    c82885: [ 25000.]
    c82900> [ 3750.]
    c82905: [ 0.]
    c82910: [ 4054.5]
    c82920: [ 4054.5]
    c82937: [ 4054.5]
    WITH OK FICA:
    1987.50 4156.00
    c82925: [ 7000.]
    c82935: [ 5012.5]
    c82880: [ 60000.]
    c82885: [ 25000.]
    c82900> [ 3750.]
    c82905: [ 0.]
    c82910: [ 4156.]
    c82920: [ 4156.]
    c82937: [ 4156.]
    """
    """
    diff --git a/taxcalc/functions.py b/taxcalc/functions.py
    index 5735d6f..6e082f7 100644
    --- a/taxcalc/functions.py
    +++ b/taxcalc/functions.py
    @@ -1508,7 +1508,7 @@ def AddCTC(_nctcr, _precrd, _earned, c07220, e00200,
    c82930 = c07220
    c82935 = c82925 - c82930
    # CTC not applied to tax
    -        c82880 = max(0, _earned)
    +        c82880 = max(0., _earned)
    if _exact == 1:
    c82880 = e82880
    c82885 = max(0., c82880 - ACTC_Income_thd)
    @@ -1518,6 +1518,7 @@ def AddCTC(_nctcr, _precrd, _earned, c07220, e00200,
    if _nctcr >= ACTC_ChildNum and c82890 < c82935:
    c82900 = 0.5 * (FICA_mc_trt + FICA_ss_trt) *\
    min(min(SS_Earnings_c, c82880), e00200)
    +        ###c82900 = 0.5 * (FICA_mc_trt * e00200 + FICA_ss_trt * min(SS_Earnings_c, e00200))
    c82905 = float((1 - ALD_SelfEmploymentTax_HC) * e03260 + e09800)
    c82910 = c82900 + c82905
    c82915 = c59660 + e11200
    """
