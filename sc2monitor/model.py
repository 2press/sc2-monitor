import enum
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Enum, Float, ForeignKey,
                        Integer, String, UniqueConstraint, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Result(enum.Enum):
    Unknown = 0
    Win = 1
    Loss = 2
    Tie = 3

    @classmethod
    def get(cls, value):
        if isinstance(value, str):
            for result in cls.__members__:
                if result[0].lower() == value[0].lower():
                    return cls[result]
        elif isinstance(value, int):
            if value == 1:
                return cls.Win
            elif value == -1:
                return cls.Loss
            elif value == 0:
                return cls.Tie

        return cls.Unknown

    def change(self):
        if self.value == 1:
            return 1.0
        elif self.value == 2:
            return -1.0
        else:
            return 0.0

    def describe(self):
        if self.value == 1:
            desc = "Win"
        elif self.value == 2:
            desc = "Loss"
        elif self.value == 3:
            desc = "Tie"
        else:
            desc = "Unknown"

        return desc

    def short(self):
        if self.value == 1:
            desc = "W"
        elif self.value == 2:
            desc = "L"
        elif self.value == 3:
            desc = "D"
        else:
            desc = "U"

        return desc

    def __str__(self):
        return self.describe()


class Race(enum.Enum):
    Random = 0
    Protoss = 1
    Terran = 2
    Zerg = 3

    @classmethod
    def get(cls, str):
        if not str:
            return cls.Random
        for race in cls.__members__:
            if race[0].lower() == str[0].lower():
                return cls[race]
        raise ValueError('Unknown race {}.'.format(str))

    def describe(self):
        if self.value == 1:
            desc = "Protoss"
        elif self.value == 2:
            desc = "Terran"
        elif self.value == 3:
            desc = "Zerg"
        else:
            desc = "Random"

        return desc

    def short(self):
        if self.value == 1:
            desc = "P"
        elif self.value == 2:
            desc = "T"
        elif self.value == 3:
            desc = "Z"
        else:
            desc = "R"

        return desc

    def __str__(self):
        return self.describe()


class Server(enum.Enum):
    Unknown = 0
    America = 1
    Europe = 2
    Korea = 3

    def describe(self):
        if self.value == 1:
            desc = "America"
        elif self.value == 2:
            desc = "Europe"
        elif self.value == 3:
            desc = "Korea"

        return desc

    def short(self):
        if self.value == 1:
            desc = "us"
        elif self.value == 2:
            desc = "eu"
        elif self.value == 3:
            desc = "kr"

        return desc

    def id(self):
        return self.value

    def __str__(self):
        return self.describe()


class League(enum.Enum):
    Unranked = -1
    Bronze = 0
    Silver = 1
    Gold = 2
    Platinum = 3
    Diamond = 4
    Master = 5
    Grandmaster = 6

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    @classmethod
    def get(cls, str):
        if not str:
            return cls.Unranked
        for league in cls.__members__:
            if league[0:1].lower() == str[0:1].lower():
                return cls[league]
        raise ValueError('Unknown league {}.'.format(str))

    def describe(self):
        if self.value == -1:
            desc = "Unranked"
        elif self.value == 1:
            desc = "Bronze"
        elif self.value == 2:
            desc = "Silver"
        elif self.value == 3:
            desc = "Gold"
        elif self.value == 4:
            desc = "Platinum"
        elif self.value == 5:
            desc = "Diamond"
        elif self.value == 6:
            desc = "Master"
        elif self.value == 7:
            desc = "Grandmaster"

        return desc

    def id(self):
        return self.value

    def __str__(self):
        return self.describe()


def same_as(column_name):
    def default_function(context):
        return context.current_parameters.get(column_name)
    return default_function


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    key = Column(String(128), unique=True)
    value = Column(String(128))

    def __repr__(self):
        output = ('<Config(id={}, key={}, value={})>')
        return output.format(self.id, self.key,
                             self.value)


class Season(Base):
    __tablename__ = "season"
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer)
    server = Column(Enum(Server), default=Server.Europe)
    year = Column(Integer)
    number = Column(Integer)
    start = Column(DateTime)
    end = Column(DateTime)

    def __repr__(self):
        output = ('<Season(id={}, season_id={}, server={},'
                  ' year={}, number={}, start={}, end={})>')
        return output.format(self.id, self.season_id,
                             self.server, self.year,
                             self.number,
                             self.start, self.end)


class Player(Base):
    __tablename__ = "player"
    __table_args__ = tuple(UniqueConstraint(
        'player_id', 'realm', 'server', 'race'))
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, default=False)
    realm = Column(Integer, default=1)
    server = Column(Enum(Server), default=Server.Europe)
    name = Column(String(64), default='')
    race = Column(Enum(Race), default=Race.Random)
    ladder_id = Column(Integer, default=0)
    league = Column(Enum(League), default=League.Unranked)
    mmr = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    refreshed = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_played = Column(DateTime)
    ladder_joined = Column(DateTime)
    last_active_season = Column(Integer, default=0)
    matches = relationship("Match",
                           back_populates="player",
                           order_by="desc(Match.datetime)",
                           cascade="save-update, merge, delete")
    statistics = relationship("Statistics",
                              back_populates="player",
                              uselist=False,
                              cascade="save-update, merge, delete")

    def __repr__(self):
        output = ('<Player(id={}, player_id={}, server={}, realm={},'
                  ' ladder={}, name={}, race={}, mmr={}, wins={}, losses={})>')
        return output.format(self.id, self.player_id,
                             self.server, self.realm,
                             self.ladder_id, self.name,
                             self.race, self.mmr,
                             self.wins, self.losses)


class Match(Base):
    __tablename__ = "match"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('player.id'))
    player = relationship(Player, back_populates="matches", uselist=False)
    result = Column(Enum(Result), default=Result.Unknown)
    datetime = Column(DateTime, default=datetime.now)
    mmr = Column(Integer, default=0)
    mmr_change = Column(Integer, default=0)
    guess = Column(Boolean, default=False)
    max_length = Column(Integer, default=180)
    ema_mmr = Column(Float, default=same_as('mmr'))
    emvar_mmr = Column(Float, default=0.0)

    def __repr__(self):
        output = ('<Match(id={}, player={}, result={},'
                  ' datetime={}, mmr={}, mmr_change={}, guess={})>')
        return output.format(self.id, self.player,
                             self.result, self.datetime,
                             self.mmr, self.mmr_change,
                             self.guess)


class Statistics(Base):
    __tablename__ = "statistics"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('player.id'))
    player = relationship(Player, back_populates="statistics", uselist=False)
    winrate = Column(Float, default=0.0)
    games = Column(Integer, default=0)
    current_mmr = Column(Integer, default=0)
    wma_mmr = Column(Integer, default=0)
    max_mmr = Column(Integer, default=0)
    min_mmr = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    longest_wining_streak = Column(Integer, default=0)
    longest_losing_streak = Column(Integer, default=0)
    guessed_games = Column(Integer, default=0)
    lr_mmr_slope = Column(Float, default=0.0)
    lr_mmr_intercept = Column(Float, default=0.0)
    sd_mmr = Column(Float, default=0.0)
    avg_mmr = Column(Float, default=0.0)
    instant_left_games = Column(Integer, default=0)

    def __repr__(self):
        output = ('<Statistics(id={}, player={})>')
        return output.format(self.id, self.player,
                             self.winrate)


class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True)  # auto incrementing
    logger = Column(String(64))  # the name of the logger. (e.g. myapp.views)
    level = Column(String(64))  # info, debug, or error?
    trace = Column(String(1024))  # the full traceback printout
    msg = Column(String(255))  # any custom log you may have included
    datetime = Column(DateTime, default=datetime.now)

    def __init__(self, logger=None, level=None, trace=None, msg=None):
        self.logger = logger
        self.level = level
        self.trace = trace
        self.msg = msg

    def __unicode__(self):
        return self.__repr__()

    def __repr__(self):
        return "<Log: {} - {}>".format(
            self.datetime.strftime('%m/%d/%Y-%H:%M:%S'), self.msg[:50])


def create_db_session(db='', encoding=''):
    if not db:
        db = 'sqlite:///sc2monitor.db'
    if not encoding:
        encoding = 'utf8'
    engine = create_engine(db, encoding=encoding)
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine
    return sessionmaker(bind=engine)()