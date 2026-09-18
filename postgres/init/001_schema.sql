CREATE TABLE IF NOT EXISTS signal_catalog (
    signal_id varchar(64) PRIMARY KEY,
    name varchar(200) NOT NULL,
    signal_type varchar(2) NOT NULL CHECK (signal_type IN ('AI', 'AO', 'DI', 'DO')),
    table_name varchar(32) NOT NULL,
    unit varchar(32),
    expected_interval_sec integer NOT NULL,
    coverage_ratio numeric(4,3) NOT NULL,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS ai_mhr (
    date_time timestamptz NOT NULL,
    data_id varchar(64) NOT NULL,
    value double precision NOT NULL,
    quality varchar(16) NOT NULL DEFAULT 'GOOD',
    PRIMARY KEY (data_id, date_time)
);

CREATE TABLE IF NOT EXISTS ao_mhr (LIKE ai_mhr INCLUDING ALL);
CREATE TABLE IF NOT EXISTS di_mhr (LIKE ai_mhr INCLUDING ALL);
CREATE TABLE IF NOT EXISTS do_mhr (LIKE ai_mhr INCLUDING ALL);

CREATE TABLE IF NOT EXISTS signal_availability (
    id bigserial PRIMARY KEY,
    data_id varchar(64) NOT NULL REFERENCES signal_catalog(signal_id),
    start_time timestamptz NOT NULL,
    end_time timestamptz NOT NULL,
    point_count bigint NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (start_time <= end_time),
    UNIQUE (data_id, start_time, end_time)
);

CREATE INDEX IF NOT EXISTS idx_signal_availability_lookup
    ON signal_availability (data_id, start_time, end_time);

CREATE TABLE IF NOT EXISTS seed_run (
    seed_key varchar(100) PRIMARY KEY,
    profile varchar(20) NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    row_count bigint
);

