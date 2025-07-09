-- Mystic Nights SQLite Schema
PRAGMA foreign_keys = ON;

CREATE TABLE servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    ip_address TEXT NOT NULL,
    player_count INTEGER DEFAULT 0,
    availability INTEGER DEFAULT 0 NOT NULL
);

CREATE TABLE channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER,
    channel_index INTEGER,
    player_count INTEGER DEFAULT 0,
    FOREIGN KEY (server_id) REFERENCES servers(id)
);

CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    rank INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lobbies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER,
    idx_in_channel INTEGER NOT NULL,
    name TEXT NOT NULL,
    password TEXT,
    player_count INTEGER DEFAULT 0,
    status INTEGER DEFAULT 1,
    map INTEGER DEFAULT 1,
    leader TEXT,
    player1_id TEXT,
    player1_character INTEGER,
    player1_status INTEGER,
    player2_id TEXT,
    player2_character INTEGER,
    player2_status INTEGER,
    player3_id TEXT,
    player3_character INTEGER,
    player3_status INTEGER,
    player4_id TEXT,
    player4_character INTEGER,
    player4_status INTEGER,

    FOREIGN KEY (channel_id) REFERENCES channels(id),
    FOREIGN KEY (player1_id) REFERENCES players(player_id),
    FOREIGN KEY (player2_id) REFERENCES players(player_id),
    FOREIGN KEY (player3_id) REFERENCES players(player_id),
    FOREIGN KEY (player4_id) REFERENCES players(player_id)
);

-- Add indices for fast lookups (optional but recommended)
CREATE INDEX idx_channels_server_id ON channels(server_id);
CREATE INDEX idx_lobbies_channel_id ON lobbies(channel_id);
CREATE INDEX idx_players_player_id ON players(player_id);

INSERT INTO servers (id, name, ip_address, player_count, availability) VALUES
  (1, 'MN0', '211.233.10.5', 0, 0),
  (2, 'MN1', '111.233.10.5', 0, 1),
  (3, 'MN2', '112.233.10.5', 0, 2),
  (4, 'MN3', '0.0.0.0', 0, -1),
  (5, 'MN4', '0.0.0.0', 0, -1),
  (6, 'MN5', '0.0.0.0', 0, -1),
  (7, 'MN6', '0.0.0.0', 0, -1),
  (8, 'MN7', '0.0.0.0', 0, -1),
  (9, 'MN8', '0.0.0.0', 0, -1),
  (10, 'MN9', '0.0.0.0', 0, -1);

-- Pre-populate 120 channels: 12 per server, server_id 1..10, channel_index 0..11
INSERT INTO channels (server_id, channel_index, player_count) VALUES
-- Server 1
(1, 0, 0),(1, 1, 0),(1, 2, 0),(1, 3, 0),(1, 4, 0),(1, 5, 0),(1, 6, 0),(1, 7, 0),(1, 8, 0),(1, 9, 0),(1,10,0),(1,11,0),
-- Server 2
(2, 0, 0),(2, 1, 0),(2, 2, 0),(2, 3, 0),(2, 4, 0),(2, 5, 0),(2, 6, 0),(2, 7, 0),(2, 8, 0),(2, 9, 0),(2,10,0),(2,11,0),
-- Server 3
(3, 0, 0),(3, 1, 0),(3, 2, 0),(3, 3, 0),(3, 4, 0),(3, 5, 0),(3, 6, 0),(3, 7, 0),(3, 8, 0),(3, 9, 0),(3,10,0),(3,11,0),
-- Server 4
(4, 0, 0),(4, 1, 0),(4, 2, 0),(4, 3, 0),(4, 4, 0),(4, 5, 0),(4, 6, 0),(4, 7, 0),(4, 8, 0),(4, 9, 0),(4,10,0),(4,11,0),
-- Server 5
(5, 0, 0),(5, 1, 0),(5, 2, 0),(5, 3, 0),(5, 4, 0),(5, 5, 0),(5, 6, 0),(5, 7, 0),(5, 8, 0),(5, 9, 0),(5,10,0),(5,11,0),
-- Server 6
(6, 0, 0),(6, 1, 0),(6, 2, 0),(6, 3, 0),(6, 4, 0),(6, 5, 0),(6, 6, 0),(6, 7, 0),(6, 8, 0),(6, 9, 0),(6,10,0),(6,11,0),
-- Server 7
(7, 0, 0),(7, 1, 0),(7, 2, 0),(7, 3, 0),(7, 4, 0),(7, 5, 0),(7, 6, 0),(7, 7, 0),(7, 8, 0),(7, 9, 0),(7,10,0),(7,11,0),
-- Server 8
(8, 0, 0),(8, 1, 0),(8, 2, 0),(8, 3, 0),(8, 4, 0),(8, 5, 0),(8, 6, 0),(8, 7, 0),(8, 8, 0),(8, 9, 0),(8,10,0),(8,11,0),
-- Server 9
(9, 0, 0),(9, 1, 0),(9, 2, 0),(9, 3, 0),(9, 4, 0),(9, 5, 0),(9, 6, 0),(9, 7, 0),(9, 8, 0),(9, 9, 0),(9,10,0),(9,11,0),
-- Server 10
(10, 0, 0),(10, 1, 0),(10, 2, 0),(10, 3, 0),(10, 4, 0),(10, 5, 0),(10, 6, 0),(10, 7, 0),(10, 8, 0),(10, 9, 0),(10,10,0),(10,11,0);

INSERT INTO players (player_id, password, rank) VALUES ('test1', '0', 199);
INSERT INTO players (player_id, password, rank) VALUES ('test2', '0', 199);
INSERT INTO players (player_id, password, rank) VALUES ('test3', '0', 199);
INSERT INTO players (player_id, password, rank) VALUES ('test4', '0', 199);

INSERT INTO lobbies (
    channel_id, idx_in_channel, name, password, player_count, status, map, leader,
    player1_id, player1_character, player1_status,
    player2_id, player2_character, player2_status,
    player3_id, player3_character, player3_status,
    player4_id, player4_character, player4_status
) VALUES
(1, 0, 'TestRoom01', NULL, 3, 1, 1, NULL,
 'test1', 1, 1,
 'test2', 2, 1,
 'test3', 3, 1,
 NULL, NULL, NULL),

(1, 1, 'TestRoom02', NULL, 4, 1, 1, 'test2',
 'test1', 1, 1,
 'test2', 2, 1,
 'test3', 3, 1,
 'test4', 4, 1),

(1, 2, 'TestRoom03', NULL, 3, 2, 1, 'test3',
 'test1', 1, 2,
 'test2', 2, 2,
 'test3', 3, 2,
 NULL, NULL, NULL);

