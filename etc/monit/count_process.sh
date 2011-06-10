# count_process soffice.bin 5 alert.txt 
# will create alert.txt if there are more than 5 instance of soffice.bin running
# for current user
declare count=$(ps ax|grep "$1"|wc|cut -c 7)
declare count=$(( $count - 1 ))
if [ $count -gt $2 ]
then
  echo $count processes for $1 > $3
fi
