## python 多进程

```python
import os
from time import sleep 
#父进程会打印，子进程不会打印这句，因为子进程从fork()的下面开始执行
print('=======================')

#在内存中开辟空间
a = 1

#父进程创建子进程，子进程完全复制父进程的代码段和内存空间，且子进程从这句代码的下面开始执行
#父进程的返回值num为子进程的PID，子进程的返回值num为0
num = os.fork()	

#如果创建子进程失败，返回值num会小于0，一般情况下不会遇到	
if num < 0:
	print('Error')

#子进程的返回值为0，会执行这部分
elif num == 0:
	print('Child process')
	print('a = ',a)	#子进程能打印出a，因为子进程完全复制父进程的代码段和内存空间

	a = 10000	#在子进程中修改a的引用

#父进程的返回值为子进程PID,执行这部分
else:
	sleep(1)
	print('Parent process')
	print('a:',a)	#父进程打印出1，不会受子进程修改引用的影响

#父子进程都会执行，父进程打印出1，子进程打印出10000
print('a = ',a)	


```

