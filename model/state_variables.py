import pandas as pd
from cadCAD_tools.types import InitialValue
from cadCAD_tools.preparation import prepare_state
from .types import Wei


genesis_states = {
    'DAI_balance': InitialValue(5900000000000000000000, Wei),
    'ETH_balance': InitialValue(30000000000000000000, Wei),
    'UNI_supply': InitialValue(30000000000000000000, Wei),
    'price_ratio': InitialValue(0, float)
}


genesis_states = prepare_state(genesis_states)