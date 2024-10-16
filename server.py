from utils import *
from time import sleep
from json import load
from random import randint
import threading
import socket

lock = threading.Lock()


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as server:
        try:
            server.bind(('', 67))
        except Exception as e:
            print(e)
            server.close()
            exit()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        configs = Configs()

        #creating 2 threads (simultaneously woking)

        # timer to expire ip assigned addresses
        thread = threading.Thread(target=timer, args=(configs.assigned, configs.ip_pool))
        thread.start()

        while True:
            # data from client
            data, client_address = server.recvfrom(1024)
            print("Connected to a client on",client_address[1])
            new_thread = threading.Thread(target=handle, args=(data, server, configs, client_address))
            new_thread.start()
            sleep(2)



#thread function 
def handle(data, server, configs, client_address):
    #server configs
    srv_conf = DHCPServer(configs, client_address)
    srv_conf.DHCPReceive(data)

    #DHCP Discover

    if data[242] == 1:
        if srv_conf.currIP is None:
            return

        #OFFER
        srv_conf.DHCPOffer()
        
        server.sendto(srv_conf.packet, client_address)

        sleep(1)

        #REQUEST
        req_data = server.recv(1024)
        srv_conf.DHCPReceive(req_data)
        sleep(1)

    if srv_conf.server_unMatch:
        return

    #ACK only sent if server and client match
    srv_conf.DHCPAck()
    server.sendto(srv_conf.packet, ('<broadcast>', client_address[1]))

    sleep(1)


class Configs:
    def __init__(self):
        self.pool_mode = ''
        self.subnet_mask = '255.255.255.224'
        self.ip_pool = []
        self.lease_time = ''
        self.reservation = dict()
        self.black_list = list()
        self.router = '192.168.1.0'
        self.server_identifier = '192.168.1.1'
        self.dns_list = ['1.1.1.1', '8.8.8.8']

        self.assigned = dict()
        self.load_conf()

        for res in self.reservation:
            ipData = IPData('res', self.reservation[res], 10 ** 20)
            self.assigned[res] = ipData

    def load_conf(self):
        f = open('configs.json')
        data = load(f)

        self.pool_mode = data['pool_mode']

        ip_pool = []
        if self.pool_mode == 'range':
            low = data['range']['from']
            high = data['range']['to']
            ip_pool = ips_range(low, high)
            ip_pool.append(high)
        elif self.pool_mode == 'subnet':
            ip_block = data['subnet']['ip_block']
            subnet_mask = data['subnet']['subnet_mask']
            ip_pool = ips_subnet(ip_block, subnet_mask)
            self.subnet_mask = subnet_mask
        self.ip_pool = ip_pool

        self.lease_time = str(data['lease_time'])

        reservation = dict()
        for mac in data['reservation_list']:
            reservation[mac] = data['reservation_list'][mac]
            if reservation[mac] in ip_pool:
                ip_pool.remove(reservation[mac])
        self.reservation = reservation

        for mac in data['black_list']:
            self.black_list.append(mac)

    def show(self):
        global lock
        with lock:
            print(self.ip_pool)
            for mac in self.assigned:
                print('hostname: {} | MAC: {} | IP: {} | EXP: {}'
                      .format(self.assigned[mac].host_name, mac_split(mac),
                              self.assigned[mac].ip, self.assigned[mac].expire_time))


class IPData:
    def __init__(self, host_name, ip, expire_time):
        self.host_name = host_name
        self.ip = ip
        self.expire_time = expire_time

    #decrements expire time
    def tick(self):
        self.expire_time = self.expire_time - 1


class DHCPServer:
    def __init__(self, configs, client_address):
        # receive
        self.transaction_ID = b''
        self.client_mac = ''
        self.host_name = ''
        self.req = False
        self.server_unMatch = False
        self.client_address = client_address
        self.client_source_ports = set()

        # extract
        self.subnet_mask = ip_to_hex(configs.subnet_mask)
        self.IP_lease_time = configs.lease_time
        self.router = ip_to_hex(configs.router)
        self.Server_ID = ip_to_hex(configs.server_identifier)
        self.dns_list = configs.dns_list
        self.dns_addresses = b''
        for dns in self.dns_list:
            self.dns_addresses += ip_to_hex(dns)

        self.lease_time = configs.lease_time

        self.assigned = configs.assigned
        self.ip_pool = configs.ip_pool
        self.black_list = configs.black_list

        # create
        self.currIP = None
        self.packet = b''

    def assign_ip(self):
        if self.client_mac in self.black_list:
            self.currIP = None
            return

        if self.client_mac in self.assigned:
            # renew
            self.assigned[self.client_mac].expire_time = int(self.lease_time)
            self.currIP = self.assigned[self.client_mac].ip
            return

        if self.req:
            ipData = IPData(self.host_name, self.currIP, int(self.lease_time))
            self.assigned[self.client_mac] = ipData
            self.ip_pool.remove(self.currIP)

        else:
            x = randint(0, len(self.ip_pool) - 1)
            ip = self.ip_pool[x]
            self.currIP = ip

    def DHCPReceive(self, data):
        if data[242] == 1:
            self.transaction_ID = data[4:8]  # in byte form
            self.client_mac = mac_to_str(data[28:34])
            nameLen = data[257]
            self.host_name = data[258:258 + nameLen].decode()
            self.assign_ip()
        elif data[242] == 3:
            if self.Server_ID == data[259:263]:
                self.transaction_ID = data[4:8]  # in byte form
                self.req = True
                self.client_mac = mac_to_str(data[28:34])
                self.assign_ip()
            else:
                self.server_unMatch = True

        # Extract and print the client's port from the client's address
        self.client_source_ports.add(self.client_address[1])

    def DHCPBody(self):
        packet = b''
        packet += b'\x02'
        packet += b'\x01'
        packet += b'\x06'
        packet += b'\x00'
        packet += self.transaction_ID
        packet += b'\x00\x00'
        packet += b'\x80\x00'
        packet += b'\x00\x00\x00\x00'
        packet += ip_to_hex(self.currIP)
        packet += b'\x00\x00\x00\x00'
        packet += b'\x00\x00\x00\x00'
        packet += mac_to_bytes(self.client_mac)
        packet += b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        packet += b'\x00' * 64
        packet += b'\x00' * 128
        packet += b'\x63\x82\x53\x63'
        return packet


    #options
    def DHCPOffer(self):
        packet = self.DHCPBody()
        packet += b'\x35\x01\x02'
        packet += b'\x01\x04' + self.subnet_mask
        packet += b'\x03\x04' + self.router
        packet += b'\x06\x08' + self.dns_addresses
        packet += b'\x33\x04' + lease_to_hex(self.IP_lease_time)
        packet += b'\x36\x04' + self.Server_ID
        packet += b'\xff'

        self.packet = packet

    def DHCPAck(self):
        packet = self.DHCPBody()
        # options
        packet += b'\x35\x01\x05'
        packet += b'\x01\x04' + self.subnet_mask
        packet += b'\x03\x04' + self.router
        packet += b'\x06\x04' + self.dns_addresses
        packet += b'\x33\x04' + lease_to_hex(self.IP_lease_time)
        packet += b'\x36\x04' + self.Server_ID
        packet += b'\xff'

        self.packet = packet


def timer(assigned_, ip_pool_):
    global lock
    while True:
        sleep(1) #every second
        temp = list(assigned_.keys()) #create dup so size doesnt change during runtime
        for mac in temp:
            assigned_[mac].tick() #expire time decremented
            if assigned_[mac].expire_time == 0:
                ip_pool_.append(assigned_[mac].ip)
                with lock:
                    del assigned_[mac]


if __name__ == '__main__':
    main()
