from common import *

instance = Instance(sys.argv[1])
demandinstance = Demandinstance(instance)

randinstance = createRandomInstance(demandinstance)

randinstance.writeinstance('random1.instance')

# for i in randinstance.trolleys:
#     print(f'{randinstance.trolleys[i].release} {randinstance.trolleys[i].deadline}')
