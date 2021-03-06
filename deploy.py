import sys
import toml
import os
import tarfile
import tempfile
import paramiko
import socket

def exit_with_error(code = 1, message = 'Something went wrong'):
	print(message)
	sys.exit(code)

def remote_exec(ssh_client, command):
	stdin, stdout, stderr = ssh_client.exec_command(command)

	strip_newlines = lambda line : line.strip()

	success = '\n'.join(map(strip_newlines, stdout))
	error = '\n'.join(map(strip_newlines, stderr))

	print(command)
	print(success)
	print(error)

	return success, error

def read_file(path):
	with open(path, 'r') as file:
		return file.read()


def deploy_to_env(service_template, script_template, run_service, caddy_service, caddyfile_template, package_archive_path, package, title, env, inventory, provision, run):
	print('Deploy to \'{}\''.format(env))
	print('Inventory: {}'.format(inventory))
	print('Provision: {}'.format(provision))
	print('Run: {}'.format(run))

	ssh = inventory['ssh']
	ssh_port = ssh['port'] if 'port' in ssh else 22
	ssh_user = ssh['user'] if 'user' in ssh else 'admin'
	ssh_password = ssh['password'] if 'password' in ssh else ''

	if 'domain' not in inventory:
		exit_with_error('No domain found!')

	if 'admin' not in inventory:
		exit_with_error('No admin found!')

	domain = inventory['domain']
	admin = inventory['admin']

	print('SSH port: {0}, username: {1}, password: {2}'.format(ssh_port, ssh_user, ssh_password))

	ssh_key = paramiko.RSAKey.from_private_key_file(filename = ssh['key'])
	ssh_client = paramiko.SSHClient()
	ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

	deploy_skipped = False

	for ip in inventory['ips']:
		print('IP: {}'.format(ip))

		try:
			ssh_client.connect(ip, port = ssh_port, username = ssh_user, password = ssh_password, timeout = 10)
		except socket.timeout:
			print('Skipping deploy: Could not connect to {}'.format(ip))
			deploy_skipped = True
			break
		except Exception as cause:
			print('Skipping deploy: {}'.format(cause))
			deploy_skipped = True
			break
		else:
			remote_exec(ssh_client, provision['command'])
			remote_path = remote_exec(ssh_client, 'pwd')[0] + '/' + package			

			print('Transfering payload...')
			sftp_client = ssh_client.open_sftp()
			sftp_client.put(package_archive_path, 'package.tar')

			service_file_content = service_template.format(title = title, path = remote_path)
			with sftp_client.file('{0}.service'.format(package), 'w') as file:
				file.write(service_file_content)

			caddy_file_content = caddyfile_template.format(domain = domain)
			with sftp_client.file('Caddyfile', 'w') as file:
				file.write(caddy_file_content)

			with sftp_client.file('caddy.service', 'w') as file:
				file.write(caddy_service)

			exec_service = run['start'].format(title = title, path = remote_path, env = env, domain = domain)
			start_script_content = script_template.format(start = exec_service)
			with sftp_client.file('start.sh', 'w') as file:
				file.write(start_script_content)

			sftp_client.close()

			print('Transfer complete!')

			unpack_tar = run_service.format(package = package, remote_path = remote_path, domain = domain, admin = admin)
			remote_exec(ssh_client, unpack_tar)

			ssh_client.close()


print('Arg Length: {0}, Args: {1}'.format(len(sys.argv), str(sys.argv)))

project_dir = sys.argv[1]
deploy_env = sys.argv[2].split('=')[1].split(',')
deploy_file = 'dPlauy.toml'
service_template = read_file('systemd_service_template.txt')
script_template = read_file('start_script_template.txt')
run_service = read_file('set_up.txt')
caddy_service = read_file('caddy.service')
caddyfile_template = read_file('Caddyfile_template.txt')

os.chdir(project_dir)
print('Changed working directory to {}'.format(os.getcwd()))

if os.path.exists(deploy_file) is False:
	exit_with_error(message = 'Could not find file \'{0}\' in {1}'.format(deploy_file, project_dir))

deploy_desc = toml.load(deploy_file)
print(deploy_desc)

if 'env' not in deploy_desc:
	exit_with_error(message = 'No environment has been defined!')

if 'run' not in deploy_desc:
	exit_with_error(message = 'No run section has been defined!')

run = deploy_desc['run']

tar_path = "{0}/dPlauy-{1}.tar".format(tempfile.gettempdir(), deploy_desc['package'])
package_tar = tarfile.open(tar_path, "w:gz")
package_tar.add(run['directory'])
package_tar.close()
print('Created temp archive at {}'.format(tar_path))

for env in deploy_env:
	if env not in deploy_desc['env']:
		exit_with_error( message = 'Could not find inventory for environment \'{}\''.format(env))
	inventory = deploy_desc['env'][env]
	deploy_to_env(service_template, script_template, run_service, caddy_service, caddyfile_template, tar_path, deploy_desc['package'], deploy_desc['title'], env, inventory, deploy_desc['provision'], deploy_desc['run'])