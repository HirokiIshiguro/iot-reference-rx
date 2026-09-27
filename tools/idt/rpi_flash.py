#!/usr/bin/env python3
"""Flash one prototype image while the separate UART helper owns the board."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import re

OWNER=Path('/tmp/codex-idt-155-owner.json')
UART='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A904CXV7-if00-port0'
HOST='ef-saffti-001-rpi-001'
def main():
    p=argparse.ArgumentParser();p.add_argument('token');p.add_argument('root');a=p.parse_args()
    raw_root=Path(a.root)
    if not re.fullmatch('[a-f0-9]{32}',a.token) or raw_root.is_symlink():
        raise RuntimeError('Invalid flash token or symbolic link directory')
    root=raw_root.resolve(strict=True)
    if root.parent != Path('/tmp') or root.name != 'codex-idt-155-flash-'+a.token:
        raise RuntimeError('Unexpected flash directory')
    owner=json.loads(OWNER.read_text())
    if socket.gethostname()!=HOST or owner['host']!=HOST or owner['uart']!=UART or owner['token']!=a.token:
        raise RuntimeError('Board lock ownership mismatch')
    os.kill(owner['pid'],0)
    def control(action):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.settimeout(15);s.connect(owner['control_socket'])
            s.sendall((json.dumps({'token':a.token,'action':action})+'\n').encode())
            answer=json.loads(s.makefile('rb').readline())
            if not answer.get('ok'):raise RuntimeError('UART control rejected: '+action)
    def call(args,timeout=90):
        subprocess.run(args,check=True,timeout=timeout)
    common=['sudo','-n','/usr/local/bin/rfp-cli','-device','RX72x','-tool','e2l:OBE110008','-if','fine','-speed','1500K','-auth','id','F'*32]
    lock=Path('/tmp/rx72n-e2lite-rfp-cli.lock.d/rfp-cli.lock')
    lock.parent.mkdir(exist_ok=True)
    base=['flock','-w','60',str(lock),*common]
    for name in ('bootloader.mot','bootloader_bank1.mot','rx72n_idt_transport.rsu','test_uart_download_rx72n.py'):
        if not (root/name).is_file():raise RuntimeError('Missing flash input: '+name)
    control('pause')
    control('mark-flashed')
    try:
        call([*base,'-erase-chip','-noquery'])
        call([*base,'-p',str(root/'bootloader.mot'),'-v','-noquery'])
        call([*base,'-p',str(root/'bootloader_bank1.mot'),'-v','-noquery'])
        import shlex
        reset=shlex.join([*base,'-sig','-run','-noquery'])
        call([sys.executable,str(root/'test_uart_download_rx72n.py'),'--rsu',str(root/'rx72n_idt_transport.rsu'),'--port',UART,'--baud','921600','--timeout','420','--post-tx-wait','120','--wait-for-ready','--ready-timeout','90','--reset-cmd',reset,'--success-message','jump to user program','--strict-success'],timeout=540)
        call([*base,'-sig','-reset','-noquery'])
        control('resume')
        call([*base,'-sig','-run','-noquery'])
        print('IDT_FLASH_COMPLETE',flush=True)
    except BaseException:
        subprocess.run([*base,'-sig','-reset','-noquery'],timeout=90,check=False)
        raise
if __name__=='__main__':main()
