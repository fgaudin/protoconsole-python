import krpc
conn = krpc.connect(name='Hello World', address='192.168.1.195')
vessel = conn.space_center.active_vessel
print(vessel.name)

