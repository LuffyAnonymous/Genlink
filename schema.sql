CREATE TABLE matches (
	id SERIAL NOT NULL, 
	club_slug VARCHAR(50) NOT NULL, 
	home_team VARCHAR(120) NOT NULL, 
	away_team VARCHAR(120) NOT NULL, 
	kickoff_at TIMESTAMP WITHOUT TIME ZONE, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_matches_club_slug ON matches (club_slug);

CREATE TABLE tickets (
	id SERIAL NOT NULL, 
	id_unique VARCHAR(255) NOT NULL, 
	supporter_id VARCHAR(100), 
	event_name VARCHAR(255), 
	event_date VARCHAR(20), 
	area_name VARCHAR(255), 
	row_name VARCHAR(255), 
	seat_name VARCHAR(255), 
	nfc VARCHAR(255), 
	owner_name VARCHAR(255), 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_tickets_id_unique ON tickets (id_unique);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	phone VARCHAR(40), 
	password_hash VARCHAR(255) NOT NULL, 
	is_approved BOOLEAN NOT NULL, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	credits INTEGER NOT NULL,
	unlimited_until TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE payment_requests (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	credits INTEGER NOT NULL,
	kind VARCHAR(20) NOT NULL,
	reference VARCHAR(32) NOT NULL,
	token VARCHAR(64) NOT NULL,
	status VARCHAR(20) NOT NULL,
	stripe_checkout_session_id VARCHAR(255),
	stripe_payment_intent_id VARCHAR(255),
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	confirmed_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE UNIQUE INDEX ix_payment_requests_token ON payment_requests (token);
CREATE UNIQUE INDEX ix_payment_requests_reference ON payment_requests (reference);
CREATE UNIQUE INDEX ix_payment_requests_stripe_checkout_session_id ON payment_requests (stripe_checkout_session_id);

CREATE TABLE credit_transactions (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	type VARCHAR(20) NOT NULL,
	amount INTEGER NOT NULL,
	description VARCHAR(255),
	payment_reference VARCHAR(255),
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE UNIQUE INDEX ix_credit_transactions_payment_reference ON credit_transactions (payment_reference);

CREATE TABLE generated_tickets (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	account_email VARCHAR(255) NOT NULL, 
	match_name VARCHAR(255) NOT NULL, 
	event_date TIMESTAMP WITHOUT TIME ZONE, 
	ticket_link TEXT NOT NULL, 
	club_slug VARCHAR(50), 
	generated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_account_match UNIQUE (user_id, account_email, match_name), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_generated_tickets_user_id ON generated_tickets (user_id);

CREATE TABLE link_generation_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	request_payload TEXT, 
	success BOOLEAN NOT NULL, 
	generated_link TEXT, 
	credits_consumed INTEGER NOT NULL, 
	external_response TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE registration_tokens (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	token VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE UNIQUE INDEX ix_registration_tokens_token ON registration_tokens (token);

