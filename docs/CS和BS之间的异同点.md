# CS和BS之间的异同点

### CS:客户端服务器架构模式

#### 优点:

​			充分利用客户端机器的资源,减轻服务器的负荷

(一部分安全要求不高的计算任务存储任务放在客户端执行，不需要把所有的计算存储都在服务器端执行,从而能够减轻服务器的压力，也能够减轻网络负荷)

#### 缺点:

​			需要安装;升级维护成本较高

### BS:浏览器服务器架构模式

#### 优点:

​			客户端不需要安装;维护成本较低

#### 缺点:

​			所有的计算和存储任务都是放在服务器端的，服务器的负荷较重;在服务端计算完反之后把结果再传输给客户端，因此客户端和服务器端会进行非常频繁的数据通信，从而网线负荷较重

# Tomcat

apchae-tomcat-8.0.42

## 目录结构说明:

bin可执行文件目录

conf配置文件目录

lib存放lib的目录

logs日志文件目录

webapps项目部署的目录

work工作目录

temp 临时目录





# servlet

### 1．设置编码

tomcat8之前,设置编码∶

1.get请求方式:

​		Tll get方式目前不需要设置编码（基于tomcat8)

​		//如果是get请求发送的中文数据,转码稍微有点麻烦(tomcat8之		前)

​		string fname = request.getParameter ( "fname");
​		

​		//1.将字符串打散成字节数组

​		byte[] bytes = fname . getBytes ("ISO-8859-1");

​		//2.将字节数组按照设定的编码重新组装成字符串

​		fname=new String(bytes, "UTF-8");

2. post请求方式:

  request.setcharacterEncoding ( "UTF-8");I+/

  //post方式下，设置编码，防止中文乱码

  

  注意：

  需要注意的是，设置编码 (post) 这一句代码必须在所有的获取参数动作之前



### 2.Servlet 继承关系

#### 继承关系:

​		Httpservlet -> Genericservlet -> servlet



1.Servlet 接口
	init()，创建 Servlet 对象后立即调用该方法完成其他初始化工作

​	service()，处理客户端请求，执行业务操作，利用响应对象响应客	户端请求。

​	destroy()，在销毁 Servlet 对象之前调用该方法，释放资源。

​	getServletConfig()，ServletConfig 是容器向 servlet 传递参数的载	体

​	getServletInfo()，获取 servlet 相关信息


2.服务方法:

​		当有请求过来时，service方法会自动响应(其实是tomcat容器调		用的)

​		在Httpservlet中我们会去分析请求的方式:到底是get、post、		head还是delete等等然后再决定调用的是哪个do开头的方法

​		那么在Httpservlet中这些do方法默认都是405的实现风格-要我		们子类去实现对应的方法

因此，我们在新建servlet时，我们才会去考虑请求方法，从而决定重写哪个do方法


### 3.生命周期

1）生命周期:

从出生到死亡的过程就是生命周期。对应servlet中的三个方法:init () , service () , destroy ()；

2）默认情况下:

第一次接收请求时，这个servlet会进行实例化(调用构造方法)、初始化(调用init())、然后服务(调用service())从第二次请求开始，每一次都是服务
当容器关闭时，其中的所有的servlet实例会被销毁，调用销毁方法3)

3）通过案例我们发现:

​		— Servlet实例tomcat只会创建一个，所有的请求都是这个实例去响应。
​		— 默认情况下，第一次请求时，tomcat才会去实例化，初始化，然后再服务

​		—这样的好处是提高系统的启动速度

​		—-/这样的缺点是第一次请求时，耗时较长

​		—因此得出结论:如果需要提高系统的启动速度，当前默认情况就是这样。如果需要提高响应速度，我们应该设置servlet的初始化时机。

4）servlet的初始化时机:
		—默认是第一次接收请求时，实例化，初始化
		—我们可以通过<load-on-startup>来设置servlet启动的先后顺序,数字越小，启动越靠前，最小值0

5）Servlet在容器中是 : 单例的、线程不安全的

​		—单例:所有的请求都是同一个实例去响应

​		—线程不安全:一个线程需要根据这个实例中的某个成员变量值去做逻辑判断。但是在中间某个时机，另一个线程改变了这个的执行路径

​		—我们已经知道了servlet是线程不安全的，给我们的启发是:尽量的不要在servlet中定义成员变量，如果不得不定义变量，就不要去：

1.修改成员变量的值 		2.不要去根据成员变量的值做一些逻辑判断

6）Servlet 3.0开始支持注解

### 4.Http协议

1）Http称之为  	超文本传输协议

2 ) Http是无状态的

3 ) Http请求响应包含两个部分:	请求	和	响应

​		—请求:

请求包含三个部分:1.请求行	;	2.请求消息头	;	 3.请求主体
1)请求行包含是三个信息︰

​			1．请求的方式﹔2.请求的URL ; 3.请求的协议（一般都是HTTP1.1)

2)请求消息头中包含了很多客户端需要告诉服务器的信息，比如:我的浏览器型号、版本、我能接收的内容的类型、我给你发的内容:

3)请求体，三种情况
			get方式，没有请求体，但是有一个querystring

​			post方式，有请求体，form data

​			json格式，有请求体，request payload响应:



 	—响应也包含三部分 ： 1．响应行	;	2.响应头	;	3.响应体

1)响应行包含三个信息:1.协议2.响应状态码(200)3.响应状态(ok)

2)响应头:包含了服务器的信息;服务器发送给浏览器的信息（内容的媒体类型、编码、内容长度等)

3)响应体:响应的实际内容(比如请求add.html页面时，响应的内容就是<html><head><body><form... .)



### 5.会话

##### 1）Http 是无状态的

 	—HTTF无状态:服务器无法判断这两次请求是同一个客户端发过来的，还是不同的客户端发过来的
 	
 	—无状态带来的现实问题:第一次请求是添加商品到购物车，第二次请求是结账;如果这两次请求服务器无法区分是同一个用户的，那么就会发生混乱
 	
 	—通过会话跟踪技术来解决无状态的问题

![image-20220426231923834](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220426231923834.png)

##### 2）会话跟踪技术

 	—客户端第一次发请求给服务器，服务器获取session，获取不到，则创建新的，然后响应给客户端
 	
 	—下次客户端给服务器发请求时，会把sessionID带给服务器，那么服务器就能获取到了，那么服务器就判断这一次请求和上次的sessionID是否相同
 	
 	—常用的API:

request.getSession () -——>获取当前的会话，没有则创建一个新的会话		request.getSession (true) -——>效果和不带参数相同
request.getSession (false)-——>获取当前会话，没有则返回null，不会创建新的
session.getId ()-——>获取sessionID
session.isNew ()-——>判断当前session是否是新的session.getMaxInactiveInterval ( )-——> session的非激活间隔时长，默认18oo秒session. setMaxInactiveInterval ( )
session.invalidate ( )-——>强制性让会话立即失效

##### 3 ) session保存作用域

- session保存作用域是和具体的某一个session对应的

- 常用的API :

  ​		void session. setAttribute (k,v)

  ​		object session.getAttribute (k)

  ​		void removeAttribute (k)

![image-20220426234628321](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220426234628321.png)

### 6．服务器内部转发以及客户端重定向

1）服务器内部转发

​				request.getRequestDispatcher (" . . . " ) . forward(request,response);

​		—一次请求响应的过程，对于客户端而言，内部经过了多少次转发，客户端是不知道的

​		—地址栏没有变化

2）客户端重定向:

​				 response.sendRedirect (" . . . " );

​		—两次请求响应的过程。客户端肯定知道请求URL有变化

​		—地址栏有变化



案例：

![image-20220427143258479](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427143258479.png)



![image-20220427141746829](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427141746829.png)

![image-20220427141448697](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427141448697.png)









![image-20220427144538650](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427144538650.png)



### 7.Thymeleaf -视图模板技术

1）添加thymeleaf的jar包

2）新建一个servlet类viewBaseservlet有两个方法

3）在web.xml文件中添加配置<context-param>

​		—配置前缀view-prefix-配置后缀view-suffix

4）使得我们的servlet继承viewBaseservlet

5)根据逻辑视图名称得到物理视图名称

//此处的视图名称是index

//那么thymeleaf会将这个逻辑视图名称对应到物理视图名称上去

//逻辑视图名称		:index

//物理视图名称  view-prefix +   逻辑视图名称   +   view-suffix
//所以真实的视图名称是: 	/			index					.html
super.processTemplate("index" , request, response);

![image-20220427152543989](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427152543989.png)

![image-20220427152621965](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427152621965.png)











#### thymeleaf的部分标签

1） 使用步骤： 添加jar ， 新建ViewBaseServlet(有两个方法） ， 配置两个<context-param> : view-prefix , view-suffix
2） 部分标签： <th:if> , <th:unless> , <th:each> , <th:text>





![image-20220427154701690](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427154701690.png)

## 8.保存作用域

原始情况下，保存作用域我们可以认为有四个： page（页面级别，现在几乎不用） , request（一次请求响应范围） , session（一次会话范围） , application（整个应用程序范围）
1） request：一次请求响应范围
2） session：一次会话范围有效
3） application： 一次应用程序范围有效

#### 演示request保存作用域

##### 客服端重定向  

请求2 获取不到uname

![image-20220427191824716](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427191824716.png)

案例：

![image-20220427193812857](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427193812857.png)

![image-20220427193851847](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427193851847.png)

##### 服务器转发

可以获取到uname

![image-20220427191806945](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427191806945.png)





案例：

![image-20220427193944653](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427193944653.png)

#### 演示session保存作用域：

第二个客服端获取不到uname 因为不是一个会话范围

![image-20220427191716538](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427191716538.png)

案例：

![image-20220427193421762](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427193421762.png)

![image-20220427193450448](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427193450448.png)



#### 演示application保存作用域

所有客服端都可以获取到uname  是公共的

![image-20220427192742572](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427192742572.png)

案例：

![image-20220427193250293](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427193250293.png)

![image-20220427193325662](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220427193325662.png)

1. 路径问题
   1） 相对路径
   2） 绝对路径
2. 实现库存系统的功能