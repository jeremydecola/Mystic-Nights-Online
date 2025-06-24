--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

-- Started on 2025-06-24 11:19:29

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 224 (class 1259 OID 16503)
-- Name: channels; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.channels (
    id integer NOT NULL,
    server_id integer,
    channel_index integer,
    player_count integer DEFAULT 0
);


ALTER TABLE public.channels OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 16502)
-- Name: channels_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.channels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.channels_id_seq OWNER TO postgres;

--
-- TOC entry 4937 (class 0 OID 0)
-- Dependencies: 223
-- Name: channels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.channels_id_seq OWNED BY public.channels.id;


--
-- TOC entry 222 (class 1259 OID 16461)
-- Name: lobbies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.lobbies (
    id integer NOT NULL,
    channel_id integer,
    idx_in_channel integer NOT NULL,
    name character varying(32) NOT NULL,
    password character varying(32),
    player_count integer DEFAULT 0,
    status integer DEFAULT 1,
    map integer DEFAULT 1,
    leader character varying(16),
    player1_id character varying(16),
    player1_character integer,
    player1_status integer,
    player2_id character varying(16),
    player2_character integer,
    player2_status integer,
    player3_id character varying(16),
    player3_character integer,
    player3_status integer,
    player4_id character varying(16),
    player4_character integer,
    player4_status integer
);


ALTER TABLE public.lobbies OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16460)
-- Name: lobbies_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.lobbies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.lobbies_id_seq OWNER TO postgres;

--
-- TOC entry 4938 (class 0 OID 0)
-- Dependencies: 221
-- Name: lobbies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.lobbies_id_seq OWNED BY public.lobbies.id;


--
-- TOC entry 220 (class 1259 OID 16431)
-- Name: players; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.players (
    id integer NOT NULL,
    player_id character varying(16) NOT NULL,
    password character varying(64) NOT NULL,
    rank integer DEFAULT 1,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.players OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16430)
-- Name: players_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.players_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.players_id_seq OWNER TO postgres;

--
-- TOC entry 4939 (class 0 OID 0)
-- Dependencies: 219
-- Name: players_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.players_id_seq OWNED BY public.players.id;


--
-- TOC entry 218 (class 1259 OID 16390)
-- Name: servers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.servers (
    id integer NOT NULL,
    name character varying(32) NOT NULL,
    ip_address character varying(16) NOT NULL,
    player_count integer DEFAULT 0,
    availability integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.servers OWNER TO postgres;

--
-- TOC entry 217 (class 1259 OID 16389)
-- Name: servers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.servers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.servers_id_seq OWNER TO postgres;

--
-- TOC entry 4940 (class 0 OID 0)
-- Dependencies: 217
-- Name: servers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.servers_id_seq OWNED BY public.servers.id;


--
-- TOC entry 4767 (class 2604 OID 16506)
-- Name: channels id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.channels ALTER COLUMN id SET DEFAULT nextval('public.channels_id_seq'::regclass);


--
-- TOC entry 4763 (class 2604 OID 16464)
-- Name: lobbies id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobbies ALTER COLUMN id SET DEFAULT nextval('public.lobbies_id_seq'::regclass);


--
-- TOC entry 4760 (class 2604 OID 16434)
-- Name: players id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.players ALTER COLUMN id SET DEFAULT nextval('public.players_id_seq'::regclass);


--
-- TOC entry 4757 (class 2604 OID 16393)
-- Name: servers id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servers ALTER COLUMN id SET DEFAULT nextval('public.servers_id_seq'::regclass);


--
-- TOC entry 4780 (class 2606 OID 16509)
-- Name: channels channels_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_pkey PRIMARY KEY (id);


--
-- TOC entry 4778 (class 2606 OID 16470)
-- Name: lobbies lobbies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobbies
    ADD CONSTRAINT lobbies_pkey PRIMARY KEY (id);


--
-- TOC entry 4774 (class 2606 OID 16438)
-- Name: players players_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_pkey PRIMARY KEY (id);


--
-- TOC entry 4776 (class 2606 OID 16440)
-- Name: players players_player_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_player_id_key UNIQUE (player_id);


--
-- TOC entry 4770 (class 2606 OID 16398)
-- Name: servers servers_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servers
    ADD CONSTRAINT servers_name_key UNIQUE (name);


--
-- TOC entry 4772 (class 2606 OID 16396)
-- Name: servers servers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servers
    ADD CONSTRAINT servers_pkey PRIMARY KEY (id);


--
-- TOC entry 4786 (class 2606 OID 16510)
-- Name: channels channels_server_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.channels
    ADD CONSTRAINT channels_server_id_fkey FOREIGN KEY (server_id) REFERENCES public.servers(id);


--
-- TOC entry 4781 (class 2606 OID 16515)
-- Name: lobbies lobbies_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobbies
    ADD CONSTRAINT lobbies_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES public.channels(id);


--
-- TOC entry 4782 (class 2606 OID 16476)
-- Name: lobbies lobbies_player1_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobbies
    ADD CONSTRAINT lobbies_player1_id_fkey FOREIGN KEY (player1_id) REFERENCES public.players(player_id);


--
-- TOC entry 4783 (class 2606 OID 16481)
-- Name: lobbies lobbies_player2_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobbies
    ADD CONSTRAINT lobbies_player2_id_fkey FOREIGN KEY (player2_id) REFERENCES public.players(player_id);


--
-- TOC entry 4784 (class 2606 OID 16486)
-- Name: lobbies lobbies_player3_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobbies
    ADD CONSTRAINT lobbies_player3_id_fkey FOREIGN KEY (player3_id) REFERENCES public.players(player_id);


--
-- TOC entry 4785 (class 2606 OID 16491)
-- Name: lobbies lobbies_player4_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.lobbies
    ADD CONSTRAINT lobbies_player4_id_fkey FOREIGN KEY (player4_id) REFERENCES public.players(player_id);


-- Completed on 2025-06-24 11:19:29

--
-- PostgreSQL database dump complete
--

