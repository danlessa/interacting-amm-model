# %%

from typing import NamedTuple, Dict, List
from dataclasses import dataclass
from cadCAD_tools import easy_run
from cadCAD_tools.preparation import prepare_params, prepare_state
import plotly.express as px
from cadCAD_tools.types import InitialValue, Param, Signal, StateUpdate, VariableUpdate
from enum import Enum
from random import random, choice
import pandas as pd

Wei = int
Percentage = float
Fiat = float


class AMM(NamedTuple):
    label: str
    transaction_fee: Percentage
    gas_fee: Fiat


@dataclass
class PairState():
    reserve_token_1: float
    reserve_token_2: float

    def __add__(self, o):
        if o == {} or o is None:
            return self
        else:
            self.reserve_token_1 += o.reserve_token_1
            self.reserve_token_2 += o.reserve_token_2
        return self


class AMM_States(dict):
    def __add__(self, o):
        missing_keys = set(self.keys()) - set(o.keys())
        for key in self.keys():
            self[key] += o.get(key, {})
        for key in missing_keys:
            self[key] = o.get(key)
        return self


UserAction = ('Skip', 'Swap', 'MintBurn')
UserActionDirection = (1, -1)


amms = [AMM('uniswap', 0.003, 20),
        AMM('honeyswap', 0.003, 0.2),
        AMM('curve', 0.0015, 10)]

initial_reserve_1 = 1000
initial_reserve_2 = 1000

pair_states = {amm.label: PairState(initial_reserve_1, initial_reserve_2)
               for amm in amms}

pair_states = AMM_States(pair_states)

initial_state = {
    'market_price_token_1': InitialValue(5.0, Fiat),
    'market_price_token_2': InitialValue(5.0, Fiat),
    'pair_state': InitialValue(pair_states, AMM_States)
}

params = {
    'amms': Param(amms, list[AMM])
}


def p_arbitrage(params, _2, _3, state) -> Signal:
    pair_states: AMM_States = state['pair_state']
    delta_pair_state = AMM_States()
    for amm_1, pair_state_1 in pair_states.items():
        for amm_2, pair_state_2 in pair_states.items():

            reserve_token_1_amm_1 = 0
            reserve_token_1_amm_2 = 0
            price_token_1 = 0
            price_token_1_amm_1 = 0
            price_token_1_amm_2 = 0

            price_token_2 = 0
            price_token_2_amm_1 = 0
            price_token_2_amm_2 = 0

            delta_pair_state[amm_1] = amm_1_arbitrage
            delta_pair_state[amm_2] = amm_2_arbitrage


    

    return {'delta_pair_state': delta_pair_state}


def p_user_action(params, _2, _3, state) -> Signal:
    pair_states: AMM_States = state['pair_state']
    delta_pair_state = AMM_States()
    for amm, pair_state in pair_states.items():

        token_1_reserve = pair_state.reserve_token_1
        token_2_reserve = pair_state.reserve_token_2

        action: str = choice(UserAction)
        direction: int = choice(UserActionDirection)

        magnitude: float = random() * 0.3
        if direction == 1:
            token_amount_1 = token_1_reserve * magnitude
            token_amount_2 = token_amount_1 * token_2_reserve / token_1_reserve
        else:
            token_amount_2 = token_2_reserve * magnitude
            token_amount_1 = token_amount_2 * token_1_reserve / token_2_reserve

        if action is 'Swap':
            token_1_reserve = -1 * token_amount_1 * direction
            token_2_reserve = token_amount_2 * direction

        elif action is 'MintBurn':
            token_1_reserve = token_amount_1 * direction
            token_2_reserve = token_amount_2 * direction
        else:
            token_1_reserve = 0
            token_2_reserve = 0

        delta_pair_state[amm] = PairState(token_1_reserve, token_2_reserve)
    return {'delta_pair_state': delta_pair_state}


def s_pair_state(params, _2, _3, state, signal) -> VariableUpdate:
    new_pair_state: AMM_States = state['pair_state']
    delta_pair_state: AMM_States = signal['delta_pair_state']
    # Sum the change on the pair states
    for amm_label, amm_pair_state in delta_pair_state.items():
        new_pair_state[amm_label] += amm_pair_state

    return ('pair_state', new_pair_state)


def brownian_motion(variable) -> StateUpdate:
    def suf(_1, _2, _3, state, _5) -> VariableUpdate:
        x = state[variable]
        raw_percent_change = (2 * random() - 1)
        percent_change = raw_percent_change * 0.1
        dx = x * percent_change
        new_x = x + dx
        return (variable, new_x)
    return suf


timestep_block = [
    {
        'label': 'Market Movements',
        'policies': {

        },
        'variables': {
            'market_price_token_1': brownian_motion('market_price_token_1'),
            'market_price_token_2': brownian_motion('market_price_token_2')
        }
    },
    {
        'label': 'AMM User Actions',
        'policies': {

            'user_action': p_user_action,
            'arbitrage': p_arbitrage
        },
        'variables': {
            'pair_state': s_pair_state
        }
    },

]

N_timesteps = 100
N_samples = 3
initial_state = prepare_state(initial_state)
params = prepare_params(params)

results = (easy_run(initial_state,
                    params,
                    timestep_block,
                    N_timesteps,
                    N_samples,
                    assign_params=False)
           .reset_index())

# %%
results.pair_state
# %%
results.market_price_token_1
# %%
px.line(results,
        x='timestep',
        y=['market_price_token_1', 'market_price_token_2'],
        facet_col='run',
        line_group='run')
# %%
print(results.pair_state.iloc[-1])

# %%

for amm in amms:
    amm_df = pd.DataFrame(results.pair_state
                          .map(lambda s: s[amm.label])
                          .tolist()
                          )

    amm_df = amm_df.add_prefix(f"{amm.label}_")
    results = results.join(amm_df)

# %%
y_cols = [f"{amm.label}_reserve_token_1" for amm in amms]

px.line(results,
        x='timestep',
        y=y_cols,
        facet_col='run',
        line_group='run')

# %%
