from pyload.core import Core
c = Core(r'C:\DATA\PyCharmProject\pyload_folders\config', r'C:\DATA\PyCharmProject\pyload_folders\temp')  #.run()

def start(x):
    print('start')
    x.run()
    print('stopped')


import threading
t = threading.Thread(target=start, args=(c,))

t.start()
#t.join()

acc = c.accountmanager.load_accounts()
print(acc)

import time

name = 'testpackage3'
folder = 'testfolder3'
root = ''
password = ''
site = 'http://asdf.com'
comment = ''
paused = None
owner = 1

url = 'http://www.share-online.biz/dl/2GUU4IXOUD'
plugin = 'ShareonlineBiz'

pkg = 1
#pkg = c.filemanager.add_package(name, folder, root, password, site, comment, paused, owner)

print(pkg)
time.sleep(0.1)

data = [(url, plugin)]

c.filemanager.add_links(data, pkg, owner)

c.filemanager.save()


info = c.filemanager.get_package_info(pkg)

print(info)

file_info = c.filemanager.get_file_info(3)

print(file_info)

#c.exit()

#time.sleep(100)

t.join()

#quit()

print('Done')
