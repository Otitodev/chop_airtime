-- Chop Airtime Database Schema
-- Run this once in the Supabase SQL editor

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table: tracks each unique user and their cumulative top-up total
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier TEXT NOT NULL UNIQUE,   -- phone number (WhatsApp) or session_id (web)
    channel TEXT NOT NULL CHECK (channel IN ('web', 'whatsapp')),
    total_received NUMERIC(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Transactions table: every top-up attempt for audit trail
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    phone_number TEXT NOT NULL,
    network TEXT NOT NULL CHECK (network IN ('MTN', 'Airtel', 'Glo', '9mobile')),
    amount NUMERIC(10, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'success', 'failed')),
    vtu_reference TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,   -- database-level double-spend guard
    vtu_response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Wallet snapshots: periodic owner wallet balance snapshots
CREATE TABLE IF NOT EXISTS wallet_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    balance NUMERIC(10, 2) NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_users_identifier ON users(identifier);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_idempotency_key ON transactions(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_snapshot_at ON wallet_snapshots(snapshot_at DESC);

-- Auto-update updated_at on users
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
