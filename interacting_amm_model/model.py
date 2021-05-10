
# Dependences
from typing import NamedTuple, Dict, List, Optional
from dataclasses import dataclass
from cadCAD_tools.preparation import prepare_params, prepare_state
from cadCAD_tools.types import InitialValue, Param, Signal, StateUpdate, VariableUpdate, ParamSweep
from random import random, choice
import numpy as np

### Simulation Configuration
N_timesteps = 150
N_samples = 5

### Abstract Definitions ###
# Units of Measurement
Wei = int
Percentage = float

# Types and Classes
class AMM(NamedTuple):
    """
    Parameters and properties of a AMM
    """
    label: str
    transaction_fee: Percentage


@dataclass
class PairState():
    """
    Representation of a AMM Pair state
    """
    reserve_token_1: float
    reserve_token_2: float

    def __add__(self, o):
        """
        Summation of two Pair States.
        """
        if o == {} or o is None:
            return self
        else:
            self.reserve_token_1 += o.reserve_token_1
            self.reserve_token_2 += o.reserve_token_2
        return self
    
    def __mul__(self, o: float):
        """
        Multiplication of a Pair State by a scalar.
        """
        self.reserve_token_1 *= o
        self.reserve_token_2 *= o
        return self


class AMM_States(dict):
    """
    Representation of a collection of AMMs for a same pair
    """
    def __add__(self, o):
        """
        Summation of two AMM_States
        """
        missing_keys = set(self.keys()) - set(o.keys())
        for key in self.keys():
            self[key] += o.get(key, {})
        for key in missing_keys:
            self[key] = o.get(key)
        return self

# Possible Actions
UserAction = ('Skip', 'Swap', 'MintBurn')
UserActionDirection = (1, -1)

### Initial State & Parameters ###

# Initial state for the AMMs
amms = [AMM('uniswap', 0.003),
        AMM('honeyswap', 0.003),
        AMM('curve', 0.0015)]

# Generate initial reserves for each AMM
initial_reserve_1 = 10000
initial_reserve_2 = 50000
pair_states = {amm.label: PairState(initial_reserve_1, initial_reserve_2)
               for amm in amms}
pair_states = AMM_States(pair_states)

amms = {amm.label: amm for amm in amms}


# For this current iteration, price = token 2 price in terms of token 1

# Simulation Initial State
initial_state = {
    'market_price': InitialValue(5, Fiat),
    'pair_state': InitialValue(pair_states, AMM_States)
}

# Simulation Parameters
params = {
    'amms': Param(amms, list[AMM]),
    'user_action_intensity': ParamSweep([0.1, 0.2], Percentage),
    'arbitrage_intensity': ParamSweep([0.0, 0.1, 0.3], Percentage),
    'swap_vs_liquidity_preference': ParamSweep([0.5, 0.9], Percentage)
}

sweep_params = {k for k, v in params.items() if type(v) is ParamSweep}

# Clean up initial state & params
initial_state = prepare_state(initial_state)
params = prepare_params(params, cartesian_sweep=True)

### Simulation Logic ###

def p_arbitrage(params, _2, _3, state) -> Signal:
    """
    Arbitrage on each individual AMM so that it rebound to the market price.
    """
    # Retrieve state and params
    arbitrage_intensity = params['arbitrage_intensity']
    pair_states: AMM_States = state['pair_state']
    market_price = state['market_price']

    delta_pair_state = AMM_States()
    for amm, pair_state in pair_states.items():
        # AMM State
        reserve_1 = pair_state.reserve_token_1
        reserve_2 = pair_state.reserve_token_2
        amm_price = reserve_2 / reserve_1

        # Optimal Token 1 value to make the AMM rebound to the market price
        price_error = amm_price + market_price
        optimal_value = (reserve_1 * market_price - reserve_2) / price_error
      

        # Optimal User Action for making the rebound
        optimal_arbitrage = PairState(-optimal_value, optimal_value * amm_price)

        # Randomize the intensity
        real_arbitrage = optimal_arbitrage * random() * arbitrage_intensity

        # Act on it
        delta_pair_state[amm] = real_arbitrage

    return {'delta_pair_state': delta_pair_state}


def p_user_action(params, _2, _3, state) -> Signal:
    """
    Take random user actions
    """
    # Retrieve state and params
    user_action_intensity = params['user_action_intensity']
    swap_vs_liquidity_preference = params['swap_vs_liquidity_preference']
    amms = params['amms']
    pair_states: AMM_States = state['pair_state']

    delta_pair_state = AMM_States()
    for amm, pair_state in pair_states.items():
        # AMM State
        amm_fee = amms[amm].transaction_fee
        token_1_reserve = pair_state.reserve_token_1
        token_2_reserve = pair_state.reserve_token_2

        # Decide if the action is going to be swap or mint/burn
        if random() < swap_vs_liquidity_preference:
            action = 'Swap'
        else:
            action = 'MintBurn'

        # Decide the direction of the swap or mint / burn
        direction: int = choice(UserActionDirection)

        # Intensity in terms of available reserve
        intensity: float = random() * user_action_intensity

        # Set the token amounts based on the sorted direction
        if direction == 1:
            token_amount_1 = token_1_reserve * intensity
            token_2_price = token_2_reserve / token_1_reserve
            token_amount_2 = token_amount_1 * token_2_price
        else:
            token_amount_2 = token_2_reserve * intensity
            token_1_price = token_1_reserve / token_2_reserve
            token_amount_1 = token_amount_2 * token_1_price 

        # Take action
        if action == 'Swap':
            if direction == 1:
                swap_fee = token_amount_1 * amm_fee
                token_amount_1 -= swap_fee
            else:
                swap_fee = token_amount_2 * amm_fee
                token_amount_2 -= swap_fee
            token_1_reserve = -1 * token_amount_1 * direction
            token_2_reserve = token_amount_2 * direction
        elif action == 'MintBurn':
            token_1_reserve = token_amount_1 * direction
            token_2_reserve = token_amount_2 * direction
        else:
            token_1_reserve = 0
            token_2_reserve = 0
        
        # Append the AMM action
        delta_pair_state[amm] = PairState(token_1_reserve, token_2_reserve)
    return {'delta_pair_state': delta_pair_state}


def s_pair_state(_1, _2, _3, state, signal) -> VariableUpdate:
    # State and signals
    new_pair_state: AMM_States = state['pair_state']
    delta_pair_state: AMM_States = signal['delta_pair_state']

    # Sum the change on the pair states
    for amm_label, amm_pair_state in delta_pair_state.items():
        new_pair_state[amm_label] += amm_pair_state

    # Assign new variable
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


def p_market_price(_1, _2, _3, state) -> Signal:
    """
    Retrieve the market price as proxied by the mean value of the AMMs
    as well as its associated volatility
    """
    pair_states: AMM_States = state['pair_state']
    prices = []
    for _, pair_state in pair_states.items():
        amm_price = pair_state.reserve_token_2 / pair_state.reserve_token_1
        prices.append(amm_price)
    return {'market_price': np.mean(prices),
            'market_price_volatility': np.std(prices)}

def generic_suf(variable) -> StateUpdate:
    def suf(params, substep, history, state, signal):
        return (variable, signal[variable])
    return suf

### Simulation Structure ###

timestep_block = [
    {
        'label': 'Market Movements',
        'policies': {
            'market_price': p_market_price

        },
        'variables': {
            'market_price': generic_suf('market_price'),
            'market_price_volatility': generic_suf('market_price_volatility'),
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

