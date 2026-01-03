from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
import subprocess
import yaml
from typing import NamedTuple, TypeVar, TypedDict

KANIDM_USER = 'idm_admin'

def kanidm(*args: str, dry_run: bool, check: bool = True, capture_output: bool = False) -> bytes:
  cmd = ['kanidm', *args, '--name', KANIDM_USER]
  print('$ ' + ' '.join(cmd))
  if not dry_run:
    return subprocess.run(cmd, check=check, capture_output=capture_output).stdout
  else:
    return b""

def kanidm_oauth(*args: str, dry_run: bool, check: bool = True, capture_output: bool = False) -> bytes:
  return kanidm('system', 'oauth2', *args, dry_run=dry_run, check=check, capture_output=capture_output)


ClientYaml = TypedDict('ClientYaml', {
  'displayname': str,
  'landing_url': str,
  'redirect_urls': list[str] | None,
  'scope_maps': dict[str, str]
})

class Client:
  name: str
  displayname: str
  landing_url: str
  redirect_urls: set[str]
  scope_maps: dict[str, set[str]]

  def __str__(self) -> str:
    return f"""{self.name}:
  displayname: {self.displayname}
  landing_url: {self.landing_url}
  redirect_urls: {"".join(f"\n    - {url}" for url in self.redirect_urls)}
  scope_maps: {"".join(f"\n    {group}: {" ".join(scopes)}" for group, scopes in self.scope_maps.items())}"""


GroupYaml = TypedDict('GroupYaml', {
  'name': str,
  'posix': bool | None
})

class Group:
  name: str
  posix: bool

  def __str__(self) -> str:
    return self.name + (" (posix)" if self.posix else "")


KanidmConfigYaml = TypedDict('KanidmConfigYaml', {
  'groups': list[GroupYaml],
  'oauth_clients': dict[str, ClientYaml]
})

class KanidmConfig(NamedTuple):
  groups: dict[str, Group]
  clients: dict[str, Client]


def read_config_yaml() -> KanidmConfig:
  with open(f'kanidm_config.yaml') as f:
    config_yaml: KanidmConfigYaml = yaml.safe_load(f)

  clients: dict[str, Client] = {}
  for client_name, client_yaml in config_yaml['oauth_clients'].items():
    client = Client()
    client.name = client_name
    client.displayname = client_yaml['displayname']
    client.landing_url = client_yaml['landing_url']
    client.redirect_urls = set(client_yaml.get('redirect_urls', []) or [])
    client.scope_maps = {
      group_name: set(scope_map.split(' '))
      for group_name, scope_map in client_yaml['scope_maps'].items()
    }
    clients[client_name] = client

  groups: dict[str, Group] = {}
  for group_yaml in config_yaml['groups']:
    group = Group()
    group.name = group_yaml['name']
    group.posix = 'posix' in group_yaml and group_yaml['posix'] == True
    groups[group.name] = group

  return KanidmConfig(clients=clients, groups=groups)


def parse_scope_map(scope_map: str) -> tuple[str, list[str]]:
  key, _, scopes = scope_map.partition(':')
  return (key.partition('@')[0], [
    scope.strip('{"} ')
    for scope in scopes.split(',')
  ])


class KanidmObject:
  fields: dict[str, list[str]]

  def __init__(self, object: str):
    self.fields = {}
    for line in object.strip().splitlines():
      key, _, value = line.partition(':')
      self.fields.setdefault(key, []).append(value.strip())

  def get_one(self, key: str) -> str:
    if key in self.fields and len(self.fields[key]) > 0:
      return self.fields[key][0]
    else:
      raise AssertionError(f"kanidm object is missing field '{key}'")

  def get_many(self, key:str) -> list[str]:
    return self.fields[key] if key in self.fields else []

  def has_key(self, key: str) -> bool:
    return key in self.fields and len(self.fields[key]) > 0

  def as_client(self) -> Client:
    client = Client()
    client.name = self.get_one('name')
    client.displayname = self.get_one('displayname')
    client.landing_url = self.get_one('oauth2_rs_origin_landing')
    client.redirect_urls = set(self.get_many('oauth2_rs_origin'))
    client.scope_maps = {
      group: set(scopes)
      for scope_map in self.get_many('oauth2_rs_scope_map')
      for group, scopes in [parse_scope_map(scope_map)]
    }
    return client

  def as_group(self) -> Group:
    group = Group()
    group.name = self.get_one('name')
    group.posix = self.has_key('gidnumber')
    return group


def list_existing_clients() -> dict[str, Client]:
  clients = (
    KanidmObject(client_str).as_client()
    for client_str in kanidm_oauth('list', dry_run=False, capture_output=True).decode().split('---')
    if len(client_str.strip()) > 0
  )
  return { client.name: client for client in clients }


def list_existing_groups() -> dict[str, Group]:
  groups = (
    KanidmObject(group_str).as_group()
    for group_str in kanidm('group', 'list', dry_run=False, capture_output=True).decode().split('---')
    if len(group_str.strip()) > 0
  )
  return { group.name: group for group in groups }


T = TypeVar('T')
class SetDiffer[T](ABC):
  def diff(self, old: set[T], new: set[T]):
    for old_item in old.difference(new):
      self.delete(old_item)
    for new_item in new.difference(old):
      self.create(new_item)

  @abstractmethod
  def create(self, new: T):
    pass

  @abstractmethod
  def delete(self, old: T):
    pass


K = TypeVar('K')
V = TypeVar('V')
class DictDiffer[K, V](ABC):
  def diff(self, old: dict[K, V], new: dict[K, V]):
    old_keys = set(old.keys())
    new_keys = set(new.keys())
    for old_key in old_keys.difference(new_keys):
      self.delete(old_key, old[old_key])
    for key in old_keys.intersection(new_keys):
      if old[key] != new[key]:
        self.update(key, old[key], new[key])
    for new_key in new_keys.difference(old_keys):
      self.create(new_key, new[new_key])

  @abstractmethod
  def create(self, key: K, new: V):
    pass

  @abstractmethod
  def update(self, key: K, old: V, new: V):
    pass

  @abstractmethod
  def delete(self, key: K, old: V):
    pass


class GroupDiffer(DictDiffer[str, Group]):
  _dry_run: bool

  def __init__(self, dry_run: bool):
    self._dry_run = dry_run

  def create(self, key: str, new: Group):
    kanidm('group', 'create', key, dry_run=self._dry_run)
    if new.posix:
      kanidm('group', 'posix', 'set', key, dry_run=self._dry_run)

  def update(self, key: str, old: Group, new: Group):
    if new.posix and not old.posix:
      kanidm('group', 'posix', 'set', key, dry_run=self._dry_run)

  def delete(self, key: str, old: Group):
    if not key.startswith('idm_'):
      print(f'Untracked group: {old}')


class RedirectUrlDiffer(SetDiffer[str]):
  _client_name: str
  _dry_run: bool

  def __init__(self, client_name: str, dry_run: bool):
    self._client_name = client_name
    self._dry_run = dry_run

  def create(self, new: str):
    kanidm_oauth('add-redirect-url', self._client_name, new, dry_run=self._dry_run)

  def delete(self, old: str):
    kanidm_oauth('remove-redirect-url', self._client_name, old, dry_run=self._dry_run)


class ScopeMapDiffer(DictDiffer[str, set[str]]):
  _client_name: str
  _dry_run: bool

  def __init__(self, client_name: str, dry_run: bool):
    self._client_name = client_name
    self._dry_run = dry_run

  def create(self, key: str, new: set[str]):
    kanidm_oauth('update-scope-map', self._client_name, key, *new, dry_run=self._dry_run)

  def update(self, key: str, old: set[str], new: set[str]):
    self.create(key, new)

  def delete(self, key: str, old: set[str]):
    kanidm_oauth('delete-scope-map', self._client_name, key, dry_run=self._dry_run)


class ClientDiffer(DictDiffer[str, Client]):
  _dry_run: bool

  def __init__(self, dry_run: bool):
    self._dry_run = dry_run

  def create(self, key: str, new: Client):
    kanidm_oauth('create', key, new.displayname, new.landing_url, dry_run=self._dry_run)
    for redirect_url in new.redirect_urls:
      kanidm_oauth('add-redirect-url', key, redirect_url, dry_run=self._dry_run)
    for group_name, scope_map in new.scope_maps.items():
      kanidm_oauth('update-scope-map', key, group_name, *scope_map, dry_run=self._dry_run)

  def update(self, key: str, old: Client, new: Client):
    if old.displayname != new.displayname:
      kanidm_oauth('set-displayname', key, new.displayname, dry_run=self._dry_run)
    if old.landing_url != new.landing_url:
      kanidm_oauth('set-landing-url', key, new.landing_url, dry_run=self._dry_run)
    RedirectUrlDiffer(key, self._dry_run).diff(old.redirect_urls, new.redirect_urls)
    ScopeMapDiffer(key, self._dry_run).diff(old.scope_maps, new.scope_maps)

  def delete(self, key: str, old: Client):
    print(f'Untracked client: {key}\n{old}')


def parse_args() -> Namespace:
  parser = ArgumentParser()
  parser.add_argument('--dry-run', action='store_true')
  return parser.parse_args()


def main(args: Namespace):
  kanidm('login', dry_run=False)

  config = read_config_yaml()

  GroupDiffer(args.dry_run).diff(list_existing_groups(), config.groups)
  ClientDiffer(args.dry_run).diff(list_existing_clients(), config.clients)


if __name__ == '__main__':
  main(parse_args())
