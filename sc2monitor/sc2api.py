import asyncio
import logging
import re
from datetime import datetime

import sc2monitor.model as model
from aiohttp import BasicAuth
from aiohttp.client_exceptions import ContentTypeError

logger = logging.getLogger(__name__)


class SC2API:

    def __init__(self, controller):
        self._controller = controller
        try:
            self._session = self._controller.http_session
        except AttributeError:
            self._session = None
        self._key = ''
        self._secret = ''
        self._access_token = ''
        self._access_token_checked = False
        self.read_config()
        self._access_token_lock = asyncio.Lock()
        self.request_count = 0
        self.retry_count = 0

        self._precompile()

    def _precompile(self):
        self._p1 = re.compile(
            r'^https?:\/\/starcraft2.com\/(?:\w+-\w+\/)?'
            r'profile\/([1-5])\/([1-2])\/(\d+)\/?',
            re.IGNORECASE)
        self._p2 = re.compile(
            r'^https?:\/\/(eu|us).battle.net\/sc2\/\w+\/'
            r'profile/(\d+)\/([1-2])\/\w+\/?',
            re.IGNORECASE)

    def read_config(self):
        self._key = self._controller.get_config(
            'api_key', raise_key_error=False)
        self._secret = self._controller.get_config(
            'api_secret', raise_key_error=False)
        new_token = self._controller.get_config(
            'access_token', raise_key_error=False)

        if self._access_token != new_token:
            self._access_token = new_token
            self._access_token_checked = False

    async def check_access_token(self, token):
        async with self._session.get(
                'https://eu.battle.net/oauth/check_token',
                params={'token': token}) as resp:
            self.request_count += 1
            self._access_token_checked = resp.status == 200
        return self._access_token_checked

    async def get_access_token(self):
        async with self._access_token_lock:
            if (not self._access_token or
                (not self._access_token_checked and
                 not await self.check_access_token(self._access_token))):
                await self.receive_new_access_token()

        return self._access_token

    async def receive_new_access_token(self):
        data, status = await self._perform_api_request(
            'https://eu.battle.net/oauth/token',
            auth=BasicAuth(
                self._key, self._secret),
            params={'grant_type': 'client_credentials'})

        if status != 200:
            raise InvalidApiResponse(status)

        self._access_token = data.get('access_token')
        self._access_token_checked = True
        self._controller.set_config('access_token', self._access_token)
        logger.info('New access token received.')

    def parse_profile_url(self, url):
        m = self._p1.match(url)
        if m:
            server = model.Server(int(m.group(1)))
            realmID = int(m.group(2))
            profileID = int(m.group(3))
        else:
            m = self._p2.match(url)
            if m:
                server = model.Server(2 if m.group(1).lower() == 'eu' else 1)
                profileID = int(m.group(2))
                realmID = int(m.group(3))
            else:
                raise ValueError('Invalid profile url {}'.format(url))
        return server, realmID, profileID

    async def get_season(self, server: model.Server):
        api_url = ('https://eu.api.blizzard.com/sc2/'
                   'ladder/season/{}')
        api_url = api_url.format(server.id())
        payload = {'locale': 'en_US',
                   'access_token': await self.get_access_token()}
        data, status = await self._perform_api_request(api_url, params=payload)
        if status != 200:
            raise InvalidApiResponse(status)

        return model.Season(
            season_id=data.get('seasonId'),
            number=data.get('number'),
            year=data.get('year'),
            server=server,
            start=datetime.fromtimestamp(int(data.get('startDate'))),
            end=datetime.fromtimestamp(int(data.get('endDate')))
        )

    async def get_metadata(self, player: model.Player):
        return await self._get_metadata(
            player.server, player.realm, player.player_id)

    async def get_ladders(self, player: model.Player):
        return await self._get_ladders(
            player.server, player.realm, player.player_id)

    async def get_ladder_data(self, player: model.Player, ladder_id):
        async for data in self._get_ladder_data(
                player.server, player.realm, player.player_id, ladder_id):
            yield data

    async def get_match_history(self, player: model.Player):
        return await self._get_match_history(
            player.server, player.realm, player.player_id)

    async def _get_ladders(self, server: model.Server,
                           realmID, profileID, scope='1v1'):
        api_url = ('https://eu.api.blizzard.com/sc2/'
                   'profile/{}/{}/{}/ladder/summary')
        api_url = api_url.format(server.id(), realmID, profileID)
        payload = {'locale': 'en_US',
                   'access_token': await self.get_access_token()}
        data, status = await self._perform_api_request(api_url, params=payload)
        if status != 200:
            raise InvalidApiResponse(status)
        data = data.get('allLadderMemberships', [])
        ladders = set()
        for ladder in data:
            if ladder.get('localizedGameMode', '').find('1v1') != -1:
                id = ladder.get('ladderId')
                if id not in ladders:
                    ladders.add(id)
        return ladders

    async def _get_metadata(self, server: model.Server,
                            realmID, profileID):
        api_url = 'https://eu.api.blizzard.com/sc2/metadata/profile/{}/{}/{}'
        api_url = api_url.format(server.id(), realmID, profileID)
        payload = {'locale': 'en_US',
                   'access_token': await self.get_access_token()}
        data, status = await self._perform_api_request(api_url, params=payload)
        if status != 200:
            raise InvalidApiResponse(status)
        return data

    async def _get_ladder_data(self, server: model.Server,
                               realmID, profileID, ladderID):
        api_url = 'https://eu.api.blizzard.com/sc2/profile/{}/{}/{}/ladder/{}'
        api_url = api_url.format(server.id(), realmID, profileID, ladderID)
        payload = {'locale': 'en_US',
                   'access_token': await self.get_access_token()}
        data, status = await self._perform_api_request(api_url, params=payload)
        if status != 200:
            raise InvalidApiResponse(status)

        league = model.League.get(data.get('league'))
        found_idx = -1
        found = 0
        used = []
        for meta_data in data.get('ranksAndPools'):
            mmr = meta_data.get('mmr')

            try:
                idx = meta_data.get('rank') - 1
                team = data.get('ladderTeams')[idx]
                player = team.get('teamMembers')[0]
                assert int(player.get('id')) == profileID
                assert int(player.get('realm')) == realmID
                used.append(idx)
            except (IndexError, AssertionError):
                found = False
                for team_idx in range(
                        found_idx + 1, len(data.get('ladderTeams'))):
                    team = data.get('ladderTeams')[team_idx]
                    player = team.get('teamMembers')[0]
                    if (team_idx not in used and
                        int(player.get('id')) == profileID and
                            int(player.get('realm')) == realmID):
                        found_idx = team_idx
                        used.append(team_idx)
                        found = True
                        break

                if not found:
                    raise InvalidApiResponse(r.url)

            if mmr != team.get('mmr'):
                logger.warning(
                    '{}: MMR in ladder request'
                    ' does not match {} vs {}.'.format(
                        api_url,
                        mmr,
                        team.get('mmr')
                    ))
                mmr = team.get('mmr')
            race = player.get('favoriteRace')
            games = int(team.get('wins')) + int(team.get('losses'))

            yield {
                'mmr': int(mmr),
                'race': model.Race.get(race),
                'games': games,
                'wins': int(team.get('wins')),
                'losses': int(team.get('losses')),
                'name': player.get('displayName'),
                'joined': datetime.fromtimestamp(team.get('joinTimestamp')),
                'ladder_id': int(ladderID),
                'league': league}

    async def _get_match_history(self, server: model.Server,
                                 realmID, profileID, scope='1v1'):
        api_url = ('https://eu.api.blizzard.com/sc2'
                   '/legacy/profile/{}/{}/{}/matches')
        api_url = api_url.format(server.id(), realmID, profileID)
        payload = {'locale': 'en_US',
                   'access_token': await self.get_access_token()}
        data, status = await self._perform_api_request(api_url, params=payload)
        if status != 200:
            raise InvalidApiResponse(status)

        match_history = []
        for match in data.get('matches', []):
            if match['type'] == scope:
                match_data = {
                    'result': model.Result[match['decision']],
                    'datetime': datetime.fromtimestamp(match['date'])}
                match_history.append(match_data)

        return match_history

    async def _perform_api_request(self, url, **kwargs):
        error = ''
        for retries in range(10):
            async with self._session.get(url, **kwargs) as resp:
                self.request_count += 1
                if resp.status == 504:
                    error = 'API timeout'
                    self.retry_count += 1
                    continue
                try:
                    json = await resp.json()
                except ContentTypeError:
                    error = 'Unable to decode JSON!'
                    self.retry_count += 1
                    continue
                json['request_datetime'] = datetime.now()
                status = resp.status
                break
        if retries == 9:
            if error:
                logger.warning(error)
            status = 0
            json = {}
        return json, status


class InvalidApiResponse(Exception):
    def __init__(self, api_url):
        self.api_url = api_url

    def __str__(self):
        return repr(self.api_url)