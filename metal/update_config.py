import json
import os
import os.path
import subprocess
import yaml
from argparse import ArgumentParser, Namespace
from jinja2 import Environment, FileSystemLoader
from typing import TypedDict, Any
from urllib.request import Request, urlopen

class ImageFactory:
  _image_cache: dict[str, str] = {}

  def get_image_id(self, hardware_name: str) -> str:
    if hardware_name not in self._image_cache:
      self._image_cache[hardware_name] = self._fetch_image_id(hardware_name)
    return self._image_cache[hardware_name]

  def _fetch_image_id(self, hardware_name: str) -> str:
    with open(f'hardware/{hardware_name}/image.yaml', 'rb') as f:
      request = Request('https://factory.talos.dev/schematics', method='POST', data=f)
      with urlopen(request) as resp:
        body = json.load(resp)
        return body['id']


class ConfigRenderer:
  _env = Environment(loader=FileSystemLoader('roles'))
  _globals: dict[str, Any] = {}

  def __init__(self) -> None:
    with open(f'secrets.yaml') as secrets_file:
      self._globals.update(yaml.safe_load(secrets_file))
    with open(f'vars.yaml') as vars_file:
      self._globals.update(yaml.safe_load(vars_file))

  def gen_config(self, role: str, **extra_vars: Any) -> str:
    template = self._env.get_template(f'{role}.yaml')
    return template.render(**self._globals, **extra_vars)

  def get_global(self, var: str) -> Any:
    return self._globals[var]


def talosctl(*args: str, dry_run: bool, ip: str | None = None):
  cmd = ['talosctl', '--talosconfig', './talosconfig', *args]
  if ip != None:
    cmd.extend(['--nodes', ip])

  print('$ ' + ' '.join(cmd))
  if not dry_run:
    subprocess.run(cmd, check=True)

def patch_config(config_file: str, patch_file: str):
  talosctl('machineconfig', 'patch', config_file, '--patch', f'@{patch_file}', '-o', config_file, dry_run=False)

def apply_config(ip: str, config_file: str, *, dry_run: bool):
  talosctl('apply-config', '--file', config_file, ip=ip, dry_run=dry_run)

def upgrade(ip: str, image_id: str, talos_version: str, *, dry_run: bool):
  talosctl('upgrade', '--image', f'factory.talos.dev/metal-installer/{image_id}:v{talos_version}', ip=ip, dry_run=dry_run)


type Inventory = dict[str, Group]
Group = TypedDict('Group', {'role': str, 'hardware': str, 'nodes': dict[str, str]})

def read_inventory(name: str) -> Inventory:
  with open(f'inventory/{name}.yaml') as f:
    return yaml.safe_load(f)



def parse_args() -> Namespace:
  parser = ArgumentParser()
  parser.add_argument('-a', '--apply', action='store_true', help='apply talos config using talosctl apply-config')
  parser.add_argument('-u', '--upgrade', action='store_true', help='upgrade talos system using talosctl upgrade')
  parser.add_argument('--dry-run', action='store_true')
  return parser.parse_args()


def main():
  args = parse_args()

  os.chdir(os.path.dirname(os.path.realpath(__file__)))
  os.makedirs('rendered', exist_ok=True)

  imageFactory = ImageFactory()
  configRenderer = ConfigRenderer()

  for group_name, group in read_inventory('prod').items():
    image_id = imageFactory.get_image_id(group['hardware'])
    for hostname, ip in group['nodes'].items():
      print(f'\n> {group_name}.{hostname} ({ip})')

      config = configRenderer.gen_config(group['role'], hostname=hostname, ip=ip, image_factory_id=image_id)
      config_filename = f'rendered/{hostname}.yaml'
      with open(config_filename, 'w') as config_file:
        config_file.write(config)

      patch_config(config_filename, f'hardware/{group['hardware']}/patch.yaml')

      if args.apply:
        apply_config(ip, config_filename, dry_run=args.dry_run)

      if args.upgrade:
        upgrade(ip, image_id, configRenderer.get_global('talos_version'), dry_run=args.dry_run)


if __name__ == '__main__':
  main()
