#!/bin/bash

if [ $(whoami) != converter ]
then
  echo start me as converter using sudo -b -u converter -s source
else
  /usr/bin/nohup /home/converter/document-chain/bin/runner -c /home/converter/converter.ini -p /home/converter/converter.pid converter  >> /home/converter/converter.log &
fi

