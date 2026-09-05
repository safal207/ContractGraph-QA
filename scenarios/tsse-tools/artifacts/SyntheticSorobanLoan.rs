#![no_std]

//! Synthetic Soroban-only fixture for the reviewed Cargo adapter tests.
//! This is not production code and is not copied from an audited target.

use soroban_sdk::{contract, contractimpl, contracttype, Env};

#[contracttype]
enum DataKey {
    Outstanding,
}

#[contract]
pub struct SyntheticSorobanLoan;

#[contractimpl]
impl SyntheticSorobanLoan {
    pub fn repay(env: Env, amount: i128) -> i128 {
        let outstanding: i128 = env.storage().persistent().get(&DataKey::Outstanding).unwrap_or(100);
        let next = outstanding.saturating_sub(amount);
        env.storage().persistent().set(&DataKey::Outstanding, &next);
        next
    }
}
