from cadCAD_tools.preparation import prepare_params
import pandas as pd
from cadCAD_tools.types import Param, ParamSweep
from pandas.core.frame import DataFrame


sys_params = {
    'fee_numerator': Param(997, int),
    'fee_denominator': Param(1000, int),
    'uniswap_events': Param(pd.read_pickle('./data/uniswap_events.pickle'), DataFrame),
    'fix_cost': Param[False, bool], # -1 to deactivate
    'retail_precision': Param(3, int),
    'retail_tolerance': Param(0.0005, float)
}

sys_params = prepare_params(sys_params)