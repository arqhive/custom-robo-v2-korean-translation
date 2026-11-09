import sys,struct
sys.path.insert(0,__import__('os').path.dirname(__file__))
from segments import *
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_BIG_ENDIAN
rom=open(__import__('os').path.join(ROOT,'Custom Robo V2 (Japan).z64'),'rb').read()
S=segments(rom)
seg=S[int(sys.argv[1])];va=int(sys.argv[2],16);n=int(sys.argv[3])
md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_BIG_ENDIAN)
p=ram_to_rom(seg,va)
for i in md.disasm(rom[p:p+4*n],va):print('%08X: %s %s'%(i.address,i.mnemonic,i.op_str))
