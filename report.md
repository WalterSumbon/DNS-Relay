[TOC]

## 响应策略

在localhost:53创建一个socket。接收/发送DNS请求/应答都通过这个端口。

接收到数据包时，对其进行解析：

如果是一个DNS请求时，有两种情况：

+ 请求的域名在配置文件中，则生成DNS应答并发送给请求方。这里如果对应的ip是`0.0.0.0`的话，需要将`flag`域改为`0x8583`。
+ 请求的域名不在配置文件中，则转发该请求给一个可靠的DNS服务器(这里选择的是114.114.114.114)，保存其transaction id和(请求方地址,请求的域名,到达时间)的映射关系到字典中。

如果是一个DNS应答，则根据其transaction id转发到对应的地址，计算所用时间，然后删除字典中对应条目。

控制台的输出在应答时进行。

## 实现细节

需要对DNS包进行解析，获知其transaction id、是请求还是应答，如果是请求的话还要知道其查询的域名。

同时，需要对于一部分DNS请求生成DNS应答。

为此实现一个接口类`DNS_Frame`，用一个DNS报文初始化该类的对象，对象负责解析该报文，通过访问该类的属性来获知DNS报文的有关信息，包括其id、name、是否是A类查询，同时该类还具有生成DNS应答的方法`generate_answer`，该方法的参数为配置文件中域名对应的ip，生成方式是将头部的各个域和问题域、回答域拼接在一起。

这些功能的实现是通过两个工具类：`DNS_Query`和`DNS_Answer_Generator`，分别用来解析DNS报文的问题部分和生成DNS报文的回答部分。之所以把他们单独拆出来是因为不管是DNS查询还是DNS应答都具有相同的头部字段，不同的只是后面的回答/问题部分。它们都有一个方法`get_bytes`来生成该部分的字节码。

最后使用一个类`DNS_Relay`使用上述的其他类的功能，实现应答逻辑。
其`namemap`属性用来保存配置文件所定义的域名到ip的映射关系。`transactions`属性用来保存`id`到`(addr,name,start_time)`的映射关系。
其`read_config`方法用来读取指定的配置文件并解析，将解析的结果放到`self.namemap`中。为了增强鲁棒性，忽略配置文件中的空行。
`run`方法创建socket并绑定，之后不断循环处理收到的报文。
为了实现并发，将报文的处理逻辑单独放到一个函数`handle`中，每次收到一个新的报文时就开启一个新的线程进行处理。

## 测试迭代

在第一版本测试的时候，发现对于config中的域名，nslookup可以正常工作，但是ping命令却显示`Ping 请求找不到主机`，使用浏览器也无法正常访问这些域名，但intercept功能可以正常运作。
猜测原因是只对查询的域名进行了筛选，而没有对查询的类型进行筛选。

第二个版本中，只对**A记录**查询做出resolve和intercept响应，其他的一律转发。
测试结果：nslookup和ping均可正常工作。

## 运行结果

配置文件：

```
0.0.0.0 pic1.zhimg.com
0.0.0.0 pic2.zhimg.com
0.0.0.0 pic3.zhimg.com
0.0.0.0 pic4.zhimg.com
0.0.0.0 static.zhimg.com
0.0.0.0 picb.zhiming.com
47.104.68.156 www.baidu.com
182.61.200.7 www.test.com
182.61.200.7 www.test1.com
202.38.86.171 www.wryyyyyy.com
119.3.231.166 www.educoder.net
```
### nslookup测试

<img src="C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20201216170118715.png" alt="image-20201216170118715" style="zoom:50%;" />

`www.wryyyyyy.com`是个不存在的网址，其余都是实际存在的网址。

控制台输出：

![image-20201216170606227](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20201216170606227.png)

![image-20201216170543370](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20201216170543370.png)

![image-20201216170519119](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20201216170519119.png)

![image-20201216170630711](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20201216170630711.png)

注意这里`Resolved`和`Intercept`都只对A类查询进行(否则会出现如前所述的问题)。所以对`www.wryyyyyy.com`和`static.zhimg.com`各有一次非A类查询采取了`Relay`处理。

### 浏览器测试

访问知乎，图片会全部裂掉：

![image-20201216171454641](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20201216171454641.png)

控制台输出：

![image-20201216171521873](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20201216171521873.png)

