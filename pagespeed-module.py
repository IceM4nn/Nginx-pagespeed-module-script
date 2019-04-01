#!/usr/bin/env python
#
# Nginx PageSpeed Module build script - By Hazmirul Afiq
# https://github.com/IceM4nn/Nginx-pagespeed-module-script
#

import os, sys, apt, urllib2, re, shutil

class LogInstallProgress(apt.progress.base.InstallProgress):
	def fork(self):
		pid = os.fork()
		if pid == 0:
			logfd = os.open("dpkg-install.log", os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o644)
			os.dup2(logfd, 1)
			os.dup2(logfd, 2)
		return pid

def download(url):
	temp_filename = url.split('/')[-1]
	f = open(temp_filename, 'wb')
	remote_file = urllib2.urlopen(urllib2.urlopen(url).geturl())

	try:
	    total_size = remote_file.info().getheader('Content-Length').strip()
	    header = True
	except AttributeError:
	    header = False # a response doesn't always include the "Content-Length" header

	if header:
	    total_size = int(total_size)

	bytes_so_far = 0

	while True:
	    buffer = remote_file.read(8192)
	    if not buffer:
	        sys.stdout.write('\n')
	        break

	    bytes_so_far += len(buffer)
	    f.write(buffer)
	    if not header:
	        total_size = bytes_so_far # unknown size

	    percent = float(bytes_so_far) / total_size
	    percent = round(percent*100, 2)
	    sys.stdout.write("Downloaded %d of %d bytes (%0.2f%%)\r" % (bytes_so_far, total_size, percent))

if __name__ == "__main__":

	print "#"
	print "# Nginx PageSpeed Module build script - By Hazmirul Afiq"
	print "# https://github.com/IceM4nn/Nginx-pagespeed-module-script"
	print "#"

	# Check if user is root first...
	if os.getuid() != 0:
		sys.exit("\n[!] Must run as root/sudo")

	# Delete older files folder
	old_folder = []
	dir_path = os.path.dirname(os.path.realpath(__file__))
	for f in os.listdir(dir_path):
		if re.search('incubator-pagespeed-ngx-(.*)-stable', f):
			old_folder.append(f)
		if re.search('nginx-(.*)',f):
			old_folder.append(f)

	if len(old_folder) != 0:
		print "\n[!] Older folder found! deleting.."
		for d in old_folder:
			print "\t- removing: "+d
			shutil.rmtree(dir_path+"/"+d)

	# Update require to get latest package
	print("\n[+] Preparing package update")
	cache = apt.Cache()
	cache.update()
	cache.open()

	# Checking for dependencies
	print "[+] Checking for dependencies"
	dep = ['unzip','gcc','make','libpcre3-dev','zlib1g-dev','nginx']
	missingPackage = []
	for i in dep:
		if cache[i].is_installed:
			print "\t- "+i+" is installed"
		else:
			print "\t! "+i+" is NOT installed"
			missingPackage.append(i)

	# Install missing dependencies
	if len(missingPackage) != 0:
		print "\n[!] Some package is missing, attempting to install."
		print "[+] Installing missing package:"
		for i in missingPackage:
			pkg = cache[i].mark_install()
			print "\t- Installing "+i
			try:
				cache.commit(install_progress=LogInstallProgress())
				print "\t- "+i+" installed succesfully"
			except Exception, e:
				print "\t! package "+i+" is failing to install"
				print "\t  "+str(e)
				sys.exit(1)

	# Get current installed nginx version
	print "\n[+] Obtaining current nginx version."
	NGINX_VERSION = cache['nginx'].versions[0].version.split('-')[0]
	print "\t- Your Nginx version is "+NGINX_VERSION

	# Downloading the source
	print "\n[+] Dowloading the source."
	url = "http://nginx.org/download/nginx-"+NGINX_VERSION+".tar.gz"
	download(url)

	# Extracting the downloaded package
	os.popen('tar zxf nginx-'+NGINX_VERSION+'.tar.gz')
	os.remove('nginx-'+NGINX_VERSION+'.tar.gz')

	# Checking the latest version of NginxPagespeedModule online
	print "\n[+] Getting latest version of Nginx Pagespeed Module."
	html = urllib2.urlopen("https://www.modpagespeed.com/doc/release_notes").read()
	NPS_VERSION = re.findall('Release (.*)-stable', html)[0]
	print "\t- The latest module version is : "+NPS_VERSION

	# Downloading the latest NPS module
	print "\n[+] Downloading the latest version NPS"
	url = "https://github.com/apache/incubator-pagespeed-ngx/archive/v"+NPS_VERSION+"-stable.zip"
	download(url)

	# Unpacking the package
	os.popen('unzip -q v'+NPS_VERSION+'-stable.zip')
	os.remove('v'+NPS_VERSION+'-stable.zip')

	# Getting PSOL URL and download it
	os.chdir('incubator-pagespeed-ngx-'+NPS_VERSION+'-stable/')
	exists = os.path.isfile("scripts/format_binary_url.sh")
	if exists:
		psol_url = os.popen('scripts/format_binary_url.sh PSOL_BINARY_URL').read()
		psol_url = str(psol_url).split('\n')[0]
		print "\n[+] Downloading PSOL"
		download(psol_url)
	else:
		print "\n[!] Something went wrong."
		print "\t- format_binary_url.sh script not found"
		sys.exit(1)

	# Extracting the package
	print "\n[+] Extracting PSOL"
	os.popen('tar -xzf $(basename '+psol_url+')')

	# Compiling the NginxPagespeed Dynamic module
	print "[+] Compiling the PageSpeed Dynamic Module. This may takes some time."
	os.chdir('../nginx-'+NGINX_VERSION)
	try:
		os.popen('./configure --add-dynamic-module=../incubator-pagespeed-ngx-'+NPS_VERSION+'-stable --with-compat').read()
		os.popen('make modules').read()
	except Exception, e:
		print "\t! Error Compiling PageSpeed Dynamic Module"
		print "\t  "+str(e)
		sys.exit(1)

	# Check the module exist and compiled successfully
	module_exist = os.path.isfile("objs/ngx_pagespeed.so")
	if module_exist:
		print "[+] Done creating module"
		module_location = str(os.getcwd())+"/objs/ngx_pagespeed.so"
		print "Module is at "+module_location
	else:
		print "[!] Something went wrong."
		sys.exit(1)

	# Copy the module
	print "\n[+] Copying nginx pagespeed module to the respective location"
	try:
		# Change the location if needed
		shutil.copyfile("objs/ngx_pagespeed.so", "/usr/lib/nginx/modules/ngx_pagespeed_"+NPS_VERSION+".so")
	except Exception, e:
		print "\t! An error has occur during copying the module"
		print "\t  "+e
		sys.exit(1)

	# Restarting Nginx to take place new module
	print "[+] Restarting nginx."
	try:
		os.popen("systemctl restart nginx").read()
	except Exception, e:
		print "\t! An error has occur when restarting nginx"
		print "\t  "+e
		sys.exit(1)

	print "[+] Script execution complete"