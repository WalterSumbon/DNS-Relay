import struct
import socket
from time import time
import threading

# parse query part
class DNS_Query:
    def __init__(self, data):
        """data -> name, querybytes, type, classify, len"""
        self.name = []
        i = 0
        length = 0
        part = ''
        while True:
            d = data[i]
            if length == 0:
                self.name.append(part)
                part = ''
                if d == 0:
                    break
                else:
                    length = int(d)
            else:
                part += chr(d)
                length -= 1
            i += 1
        self.name = '.'.join(self.name[1:])
        self.querybytes = data[0:i + 1]
        self.type, self.classify = struct.unpack('>HH', data[i + 1:i + 5])  # '>' : 大端; H: unsigned short
        self.len = i + 5
    def get_bytes(self):
        return self.querybytes + struct.pack('>HH', self.type, self.classify)

# generate answer part
class DNS_Answer_Generator:
    def __init__(self, ip):
        self.name = 0xc00c  # a pointer to position 0c
        self.type = 1
        self.classify = 1
        self.timetolive = 200
        self.datalength = 4
        self.ip = ip        # str
    def get_bytes(self):
        """ip -> DNS response: bytes"""
        res = struct.pack('>HHHLH', self.name, self.type, self.classify, self.timetolive, self.datalength)
        s = self.ip.split('.')
        res = res + struct.pack('BBBB', int(s[0]), int(s[1]), int(s[2]), int(s[3])) # B: unsigned char
        return res

class DNS_Frame:
    def __init__(self, data):
        self.id, self.flags, self.quests, self.answers, self.author, self.addition = struct.unpack('>HHHHHH', data[0:12])
        self.is_query = not (self.flags & 0x8000)
        if self.is_query:
            self.query_part = DNS_Query(data[12:])
            # self.answer_part = None
        else:
            self.query_part = None
            # self.answer_part = ...

    def get_id(self):
        return self.id
    def get_name(self):
        return self.query_part.name
    def is_A(self):
        return self.query_part.type == 1
    def is_AAAA(self):
        return self.query_part.type == 28
    # def get_ip(self):
    #     return self.answer_part.ip  

    def generate_answer(self, ip):
        self.answer = DNS_Answer_Generator(ip)
        self.answers = 1
        self.flags = 0x8180 if ip != '0.0.0.0' else 0x8583 # standard query response

        res = struct.pack('>HHHHHH', self.id, self.flags, self.quests, self.answers, self.author, self.addition)
        res += self.query_part.get_bytes()
        res += self.answer.get_bytes()
        return res

class DNS_Relay:
    def __init__(self,config = 'config'):
        self.config = config
        self.namemap = {} # dict<name:str, ip:str>
        self.read_config()

        self.nameserver = ('114.114.114.114',53)

        self.transactions = {} #dict<id: int, tuple<addr,name, start_time>>

    def read_config(self):
        with open(self.config, 'r') as f:
            for line in f:
                if line.strip() != '':
                    ip, name = line.split(' ')
                    self.namemap[name.strip()] = ip.strip()

    def handle(self,s,data,addr):
        start_time = time()
        dns_frame = DNS_Frame(data)
        id = dns_frame.get_id()

        if dns_frame.is_query:
            name = dns_frame.get_name()

            if name in self.namemap and dns_frame.is_A():
                ip = self.namemap[name]
                response = dns_frame.generate_answer(ip)
                s.sendto(response,addr)
                print('%+50s'%name,end='\t')
                if ip == '0.0.0.0':
                    print('INTERCEPT','%fs'%(time()-start_time),sep='\t')
                else:
                    print(' RESOLVED','%fs'%(time()-start_time),sep='\t')
            else:
                s.sendto(data, self.nameserver)
                self.transactions[id] = (addr, name, start_time)
        else:
            if id in self.transactions:
                target_addr, name, start_time = self.transactions[id]
                s.sendto(data, target_addr)
                print('%+50s'%name, '    RELAY','%fs'%(time()-start_time),sep='\t')
                del self.transactions[id]

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('0.0.0.0', 53))
        while True:
            try:
                data, addr = s.recvfrom(2048)
                threading.Thread(target=self.handle, args=(s,data, addr,)).start()
            except Exception:
                pass

if __name__ == '__main__':
    dns_relay = DNS_Relay('config2.txt')
    dns_relay.run()