# javaweb

## html

### 1.form表单

input type="text"表示文本框，其中name属性必须要指定，否则这个文本框的数据将来是不会发送给服务器的

input type="password"表示密码框

input type="radio"表示单选按钮。需要注意的是，name属性值保持一 致， 这样才会有互斥的效果;可以通过checked属性设置默认选中的项

input type=" checkbox"表示复选框。name属性值建议保持一致， 这样将来我们服务器端获取值的时候获取的是-一个数组

select表示下拉列表。每一个选项是option,其中value属 性是发送给服务器的值，selected表示默认选中的项

textarea表示多行文本框(或者称之为文本域) , 它的value值就是开始结束标签之间的内容

##### 案例：

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>form</title>
</head>
<body>
  <form action="发往目的地" method="post">
      昵称: <input type="text" name="nickName" value="请输入您的昵称"/><br/>
      密码: <input type="password" name="psw"/><br/>
      性别: <input type="radio" name="gender" value="male" checked/>男
            <input type="radio" name="gander" value="female" />女<br/>
      爱好:<input type="checkbox" name="hobby" value="basketball" checked/>篮球
      <input type="checkbox" name="hobby" value="football" />足球
      <input type="checkbox" name="hobby" value="volleyball" />排球<br/>
      星座: <select>
                <option>白羊座</option>
                <option>水瓶座</option>
      <option selected>双子座</option>
      <option>巨蟹座</option>
            </select><br/>
      备注:<textarea name="remark" rows="4" cols="50"></textarea><br/>
      <input type="submit" value="注 册" />
      <input type="reset" value="重置" />

  </form>

</body>
</html>
```

### 2.frameset

![image-20220419150053048](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220419150053048.png)

![image-20220419150526430](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220419150526430.png)

### 3.iframe

![image-20220419150736851](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220419150736851.png)

![image-20220419150721165](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220419150721165.png)





![image-20220419194328559](C:\Users\23378\AppData\Roaming\Typora\typora-user-images\image-20220419194328559.png)