SET search_path TO 'users';
CREATE INDEX accounts_lower_address_idx ON accounts ((lower(address)));
CREATE INDEX accounts_unconfirmed_lower_address_idx ON accounts_unconfirmed ((lower(address)));