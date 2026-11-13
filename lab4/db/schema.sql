CREATE TABLE IF NOT EXISTS flights (
    id          BIGSERIAL PRIMARY KEY,
    carrier     TEXT          NOT NULL,
    flight_no   TEXT          NOT NULL,
    origin      CHAR(3)       NOT NULL,
    destination CHAR(3)       NOT NULL,
    dep_time    TIMESTAMP     NOT NULL,
    arr_time    TIMESTAMP     NOT NULL,
    price       NUMERIC(10,2) NOT NULL CHECK (price > 0),
    CHECK (origin <> destination),
    CHECK (arr_time > dep_time),
    UNIQUE (carrier, flight_no, dep_time)
);

-- выборка рейсов за дату: dep_time >= :день AND dep_time < :день + 1
CREATE INDEX IF NOT EXISTS flights_dep_time_idx ON flights (dep_time);
