import json
import os
import os.path
import subprocess
import yaml
from argparse import ArgumentParser, Namespace
from glob import glob
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
  _env = Environment(loader=FileSystemLoader('.'))
  _vars: dict[str, Any] = {}

  def __init__(self) -> None:
    with open(f'vars.yaml') as vars_file:
      self._vars = yaml.safe_load(vars_file)

  def _render_patch(self, name: str, path: str, **extra_vars: Any) -> str:
    template = self._env.get_template(path)
    outfile = f'rendered/{name}_{path.replace("/", "_")}.yaml'
    with open(outfile, 'w') as f:
      f.write(template.render(**self._vars, **extra_vars))
    return outfile

  def gen_config(self, name: str, role: str, hardware: str, **extra_vars: Any) -> str:
    patch_args: list[str] = [
      arg
      for path in [
        *glob(f'roles/common/*.yaml'),
        *glob(f'roles/{role}/*.yaml'),
        *glob(f'hardware/{hardware}/patch/*.yaml')
      ]
      for arg in ['--config-patch', '@' + self._render_patch(name, path, **extra_vars)]
    ]

    outfile = f'rendered/{name}.yaml'
    talosctl(
      'gen', 'config', self.get_global('cluster_name'), self.get_global('cluster_endpoint'),
      '--with-secrets', 'secrets.yaml',
      '--kubernetes-version', self.get_global('kubernetes_version'),
      '--talos-version', self.get_global('talos_version'),
      *patch_args,
      '--output-types', role,
      '--output', outfile,
      '--force', dry_run=False)
    return outfile

  def get_global(self, var: str) -> Any:
    return self._vars[var]


def talosctl(*args: str, dry_run: bool, ip: str | None = None):
  cmd = ['talosctl', *args]
  if ip != None:
    cmd.extend(['--nodes', ip])

  print('$ ' + ' '.join(cmd))
  if not dry_run:
    subprocess.run(cmd, check=True)

def validate_config(config_file: str):
  talosctl('validate', '--config', config_file, '--mode', 'metal', '--strict', dry_run=False)

def apply_config(ip: str, config_file: str, *, dry_run: bool):
  dry_run_arg = ['--dry-run'] if dry_run else []
  talosctl('apply-config', '--talosconfig=./talosconfig', '--file', config_file, *dry_run_arg, ip=ip, dry_run=False)

def upgrade(ip: str, image_id: str, talos_version: str, *, dry_run: bool):
  talosctl('upgrade', '--talosconfig=./talosconfig', '--image', f'factory.talos.dev/metal-installer/{image_id}:v{talos_version}', ip=ip, dry_run=dry_run)


type Inventory = dict[str, Group]
Group = TypedDict('Group', {'role': str, 'hardware': str, 'nodes': dict[str, str]})

def read_inventory(name: str) -> Inventory:
  with open(f'inventory/{name}.yaml') as f:
    return yaml.safe_load(f)


def parse_args() -> Namespace:
  parser = ArgumentParser()
  parser.add_argument('-a', '--apply', action='store_true', help='apply talos config using talosctl apply-config')
  parser.add_argument('-u', '--upgrade', action='store_true', help='upgrade talos system using talosctl upgrade')
  parser.add_argument('--group', action='store', default=None, help='only operate on nodes in the specified group')
  parser.add_argument('--role', action='store', default=None, help='only operate on nodes with the specified role')
  parser.add_argument('--hardware', action='store', default=None, help='only operate on nodes with the specified hardware')
  parser.add_argument('--dry-run', action='store_true')
  return parser.parse_args()


def main():
  args = parse_args()

  os.chdir(os.path.dirname(os.path.realpath(__file__)))
  os.makedirs('rendered', exist_ok=True)

  imageFactory = ImageFactory()
  configRenderer = ConfigRenderer()

  inventory = {
    group_name: group
    for group_name, group in read_inventory('prod').items()
    if args.group == None or group_name == args.group
    if args.role == None or group['role'] == args.role
    if args.hardware == None or group['hardware'] == args.hardware
  }

  for group_name, group in inventory.items():
    image_id = imageFactory.get_image_id(group['hardware'])
    for hostname, ip in group['nodes'].items():
      print(f'\n> {group_name}.{hostname} ({ip})')
      if not args.dry_run:
        input()

      config_filename = configRenderer.gen_config(hostname, group['role'], group['hardware'],
                                                  hostname=hostname, ip=ip, image_factory_id=image_id)

      validate_config(config_filename)

      if args.apply:
        apply_config(ip, config_filename, dry_run=args.dry_run)

      if args.upgrade:
        upgrade(ip, image_id, configRenderer.get_global('talos_version'), dry_run=args.dry_run)


if __name__ == '__main__':
  main()
