# Go指南 - 笔记

## 一、基础

### 1.包

每个Go程序都是由包构成的。

程序从main包开始运行。

> 包名与导入路径的最后一个元素一致

### 2.导入

分组导入：使用圆括号组合导入。推荐分组导入。

### 3.导出名

> 在Go中，如果一个名字以大写字母开头，那么它就是已导出的。

只能导入已导出的名字；任何未导出的名字在该包外均无法访问。

### 4.函数

函数可以没有参数或接受多个参数。

> 类型在变量名之后。

当连续两个或多个函数的已命名形参类型相同时，除最后一个外，其他的都可省略。

```
func add (x, y int) int {
    return x + y
}
```

函数可以返回多值：

```
func swap(x, y string) (string, string) {
    return y, x
}

func main() {
    a, b := swap("hello", "world")
}
```

Go的返回值可被命名，它们会被视作定义在函数顶部的变量。

没有参数的`return`语句返回已命名的返回值。

仅用在短函数中，否则影响代码可读性。

```
func split(sum int) (x, y int) {
    x = sum * 4 / 9
    y = sum - x
    return
}
```

### 5.变量

`var`语句用于声明一个变量列表，类型在表达式后面。

多个连续相同的变量也可以按照函数参数一样的方式只在最后一个指定类型。

变量声明可以包含初始值，每个变量对应一个。如果初始值已存在，则可以省略类型。

```
var i, j int = 1, 2
```

**只能在函数中使用`:=`**在类型明确的地方代替`var`声明。

### 6.基本类型

```
bool

string

int int8 int16 int32 int64
uint uint8 uint16 uint32 uint64 uintptr

byte // uint8

rune // int32

float32 float64

complex64 complex128
```

`int`，`uint`，`uintptr`在32位系统上通常为32位宽，64位系统上则为64位宽。

> 没有明确初始值的变量声明会被赋予它们的零值：
>
> - 数值类型为`0`
> - 布尔类型为`false`
> - 字符串为`""`(空字符串)

表达式`T(v)`将值`v`转换为类型`T`。

```
i := 3
f := float64(i)
```

### 7.常量

使用`const`关键字。不能使用`:=`语法。

## 二、流程控制语句

### 1.for

> Go只有一种循环结构：`for`循环。

基本的`for`循环由三部分组成，它们用分号隔开：
初始化语句：在每一次迭代前执行；通常为短变量声明，该变量仅在`for`语句作用域中可见
条件表达式：在每次迭代前求值；一旦表达式的布尔值为`false`，迭代就会终止
后置语句：在每次迭代的结尾执行

```
for i := 0; i < 10; i++ {  }

// 初始化语句和后置语句是可选的
// 相当于while循环
j := 1
for j < 10 {  }

// 无限循环
for {  }
```

> Go的for语句后面的三个构成部分外没有小括号，大括号`{}`则是必须的。

### 2.if

> Go的`if`语句与`for`循环类似，表达式外无需小括号，而大括号`{}`是必须的。

`if`语句可以在条件表达式之前执行一个简单的语句，该语句声明变量的作用域仅在`if`之内(包括它的else块)。

```
if y := x * x; y > 100 { }
```

### 3.switch

Go会自动终止`case`分支，想要不终止需要`fallthrough`语句结束。

`case`可以是表达式。

`switch`的`case`语句从上到下顺次执行，直到匹配成功时停止。

`switch`的条件可以为`true`，或者说没有条件；此时相当于`if else`语句。

### 4.defer

`defer`语句会将函数推迟到外层函数返回之后执行。

推迟调用的函数其参数会立即求值，但直到外层函数返回前该函数都不会被调用。

```
defer fmt.Println("world")fmt.Println("hello")
```

推迟的函数调用会被压入一个栈中，当外层函数返回时，被推迟的函数会按照先进后出的顺序调用。

```
for i := 0; i < 10; i++ {    defer fmt.Println(i)}// 结果： 9 8 7 6 5 4 3 2 1 0
```

## 三、struct、slice和映射等

### 1.指针

> Go拥有指针。指针保存了值的内存地址。
> Go没有指针运算。

类型`*T`是指向`T`类型值的指针。其零值为`nil`。

```
var p *intfmt.Println(p)// <nil>
```

`&`操作符会生成一个指向其操作数的指针。

```
i := 1p = &ifmt.Println(p)// 0x416038
```

`*`操作符表示指针指向的底层值。这就是通常所说的“间接引用”或“重定向”。

```
fmt.Println(*p) // 通过指针 p 读取 i*p = 21         // 通过指针 p 设置 i
```

### 2.结构体（struct）

> 一个结构体（struct）就是一组字段（field）。
> 结构体字段用点号来访问。

```
type Vertex struct {    X int    Y int}func main() {    fmt.Printin(Vertex{1, 2}) // {1 2}    v.X = 4    fmt.Println(v.X) // 4}
```

结构体字段可以通过结构体指针来访问。

允许隐式间接引用（不写`*`号）：

```
v := Vertex{1, 2}p := &vfmt.Println(p.X) // 1
```

### 3.数组

类型`[n]T`表示拥有n个T类型的值的数组。

**切片**为数组元素提供动态大小的、灵活的视角。切片比数组更常用。

类型`[]T`表示一个元素类型为`T`的切片。

切片通过两个下标来界定，即一个上界和一个下界，二者以冒号分隔：

```
arr[low: high]
```

它会选择一个半开区间，包括第一个元素，排除最后一个元素。

```
primes := [6]int{2, 3, 5, 7, 11, 13}var s []int = primes[1:4]fmt.Println(s)// [3 5 7]
```

> 切片就像数组的引用

切片并不存储任何数据，它只是描述了底层数组中的一段。
**更改切片的元素会修改其底层数组中对应的元素**。
与它共享底层数组的切片都会观测到这些修改。

切片文法类似于没有长度的数组文法。

```
[]bool {true, false, true}
```

上面的代码会创建一个数组，然后构建了这个引用这个数组的一个切片。

下面是一个结构体切片：：

```
s := []struct {    i int    b string} {    {1, "a"},    {2, "b"},    {3, "c"},    {4, "d"},    {5, "e"},}fmt.Println(s)// [{1 a} {2 b} {3 c} {4 d} {5 e}]
```

在进行切片时，可以利用它的默认行为来忽略上下界。
切片下界默认值为0，上界则是该切片的长度。

对于数组：

```
var a [10]int// 以下切片是等价的a[0:10]a[:10]a[0:]a[:]
```

> 切片拥有**长度**和**容量**。
> 切片的长度就是它所包含的元素的个数。
> 切片的容量是从它的第一个元素开始数，到其底层数组元素末尾的个数。
> 切片的零值是`nil`，长度和容量为0且没有底层数组。

切片`s`的长度可以通过表达式`len(s)`，容量通过`cap(s)`来获取。
可以通过重新切片来扩展一个切片，给它足够的容量。

```
s := []int{2, 3, 5, 7, 11, 13}// len=6 cap=6 [2 3 5 7 11 13]// 截取切片使其长度为 0s = s[:0]// len=0 cap=6 []// 拓展其长度s = s[:4]// len=4 cap=6 [2 3 5 7]// 舍弃前两个值s = s[2:]// len=2 cap=4 [5 7]
```

`make([]T, length, cap)`函数会分配一个元素为零值的数组并返回一个引用了它的切片。

```
a := make([]int, 5)// len(a) = 5// a = [0 0 0 0 0]
```

`append(arr []T, val1<T>, val2<T>, val3<T>...) []T`函数可以为切片追加新元素。

```
var s []ints = append(s, 1, 2)// s = [1 2]
```

> `for`循环的`range`形式可遍历切片或映射。
> 每次迭代返回 第一个值为当前元素的下标，第二个值为该元素对应元素的一份副本。
> 可用`_`来代替`i`或者`v`来忽略其值。

```
pow := []int{1, 2, 4, 8, 16, 32, 64, 128}for i, v := range pow {    fmt.Printf("2**%d = %d\n", i, v)}// 2**0 = 1// 2**1 = 2// 2**2 = 4// 2**3 = 8// 2**4 = 16// 2**5 = 32// 2**6 = 64// 2**7 = 128
```

### 4.映射

> 映射将键映射到值。
> 映射的零值为`nil`。`nil`映射既没有键，也不能添加键。
> `make`[1]函数会返回给定类型的映射，并将其初始化备用。
> 映射的文法与结构体相似，不过必须有键名[2]。
> 若顶级类型只是一个类型名，可以在文法中省略[3]它。

```
type User struct {	Id int	Name string}func main() {    // 1. make 函数构建    u := make(map[string]User)	u["第一名"] = User{ 1, "John Lee", }	u["第二名"] = User{ 2, "Bob Zhang", }	fmt.Println(u)	// map[第一名:{1 John Lee} 第二名:{2 Bob Zhang}]		// 2. 直接赋值	u2 := map[string]User {	    "特等奖": User{ 3, "Lily Wong" },	}	fmt.Println(u2)	// map[特等奖:{3 Lily Wong}]		// 3. 省略类型	u3 := map[string]User {	    "特困生": { 4, "Sam Liu" },	}	fmt.Println(u3)	// map[特困生:{4 Sam Liu}]}
```

映射中插入或修改元素：

```
m[key] = elem
```

获取元素：

```
elem = m[key]
```

删除元素：

```
delete(m, key)
```

通过双赋值检测某个键是否存在：

```
// 若 key 在 m 中，ok 为 true，否则为 false。// 若 key 不在映射 m 中，那么 elem 是该映射元素类型的零值。elem, ok = m[key]
```

### 5.函数

> Go函数可以是一个闭包。
> 闭包是一个函数值，它引用了其函数体之外的变量。
> 该函数可以访问并赋予其引用的变量的值。

```
// 斐波纳契数列func fibonacci() func(int) []int {	arr := []int{}	return func(i int) []int {		if i <= 1 {			arr = append(arr, i)		} else {			arr = append(arr, arr[i - 1] + arr[i - 2])		}		return arr	}}func main() {	f := fibonacci()	var result []int	for i := 0; i < 10; i++ {		result = f(i)	}	fmt.Println(result)	// [0 1 1 2 3 5 8 13 21 34]}
```

## 四、方法和接口

### 1.方法

> **Go没有类。**

> 可以为结构体类型定义方法。
> 方法就是一类带特殊**接收者**参数的函数。
> **方法即函数。**
> 方法接收者在它自己的参数列表内，位于`func`关键字和方法名之间。

```
type Vertex struct {    X, Y float64}func (v Vertex) Abs() float64 {    return math.Sqrt(v.X * v.X + v.Y * v.Y)}func main() {    v := Vertex{3, 4}    fmt.Println(v.Abs())    // Result: 5}
```

也可以为非结构体类型声明方法。

> 接收者的类型定义和方法**必须在同一包内**，**不能为内建类型声明方法**。

```
type MyFloat float64func (f MyFloat) Abs() float64 {    if f < 0 {        return float64(-f)    }    return float64(f)}func main() {    f := MyFloat(-math.Sqrt(2))    fmt.Println(f.Abs())    // Result: 1.4142135623730951}
```

可以为指针接收者声明方法。
对于某类型`T`，接收者的类型可以用`*T`的文法。但是`T`不能是`*int`这样的指针。
方法必须使用指针接收者来更改声明的原始值[4]。

> 使用指针接收者的原因有二：
>
> - 方法能够修改其接收者指向的值
> - 这样可以避免在每次调用方法时复制该值。若值为大型结构体时，这样做更加高效。

```
type Vertex strcut {    X, Y float64}func (v Vertex) Abs() float64 {    return math.Sqrt(v.X * v.X + v.Y * v.Y)}func (v *Vertex) Scale(f float64) {    v.X = v.X * f    v.Y = v.Y * f}func main() {    v := Vertex{3, 4}    v.Scale(10)    fmt.Println(v.Abs())    // Result: 50    // [4]: 如果我们把 Scale 方法的 * 去掉    // 结果又变成了 5}
```

> 带指针参数的函数必须接受一个指针（带指针类型参数的函数，其参数必须是指针）。
>
> ```
> var v VertexScaleFunc(v, 5)  // 编译错误！ScaleFunc(&v, 5) // OK
> ```
>
> 而以指针为接收者的方法被调用时，接收者既能为值又能为指针。
>
> ```
> var v Vertexv.Scale(5) // OKp := &Vp.Scale(10) // OK
> ```

同理，接受一个值作为参数的函数必须接受一个指定类型的值。

```
var v VertexAbsFunc(v) // OKAbsFunc(&v) // 编译错误！
```

而以值为接收者的方法被调用时，接收者既能为值又能为指针。

```
var v Vertexv.Abs() // OKp := &vp.Abs() // OKtype Vertex struct {    X, Y float64}func (v Vertex) Abs() float64 {    reutrn math.Sqrt(v.X * v.X + v.Y * v.Y)}func AbsFunc(v Vertex) float64 {    return math.Sqrt(v.X * v.X + v.Y * v.Y)}func main() {    v := Vertex{3, 4}    fmt.Println(v.Abs())     // 5    fmt.Println(AbsFunc(v))  // 5        p := &Vertex{4, 3}    fmt.Println(p.Abs())     // 5    fmt.Println(AbsFunc(*p)) // 5}
```

### 2.接口

```
type I interface {    [funcs]()}
```

> **接口类型`interface`**是由一组方法签名定义的集合。
> 接口类型的变量可以保存任何实现了这些方法的值。

```
type I interface {    M()}type T struct {    S string}// 此方法表示类型T实现了接口I，但我们无需显式声明此事func (t T) M() {    fmt.Println(t.S)}func main() {    var i I = T{"Hello"}    i.M() // Result: Hello}
```

> 接口也是值。
> 接口可以像其它值一样传递。
> 接口值也可以用作函数的参数或返回值。

在内部，接口值可以看做包含值和具体类型的元组:

```
(value, type)
```

接口值保存了一个具体底层类型的具体值。
接口值调用方法时会执行其底层类型的同名方法。

```
type I interface {    M()}type T struct {    S string}func (t *T) M() {    fmt.Println(t.S)}type F float64func (f F) M() {    fmt.Println(f)}func describe(i I) {    fmt.Printf("(%v, %T)\n", i, i)}func main() {    var i I        i = &T{"Hello"}    describe(i) // (&{Hello}, *main.T)    i.M()       // Hello        i = F(math.Pi)    describe(i) // (3.141592653589793, main.F)    i.M()       // 3.141592653589793}
```

> 底层值为`nil`的接口值。
> 即便接口内的具体值为`nil`，方法仍然会被`nil`接收者调用。
> **保存了`nil`具体值的接口其自身并不为`nil`。**

```
type I interface {    M()}type T struct {    S string}func (t *T) M() {    if t == nil {        fmt.Println("<nil>")        return    }    fmt.Println(t.S)}func describe(i I) {	fmt.Printf("(%v, %T)\n", i, i)}func main() {    var i I        // nil接口值既不保存值也不保存具体类型。    // 为nil接口调用方法会产生运行时错误，因为接口的元组内并未包含能够指明该调用哪个具体方法的类型。    describe(i) // (<nil>, <nil>)    i.M()       // 编译错误！        var t *T    i = t    describe(i) // (<nil>, *main.T)    i.M()       // <nil>        i = &T{"Hello"}    describe(i) // (&{hello}, *main.T)    i.M()       // hello}
```

> 指定了零个方法的接口值被称为**空接口**。

```
interface {}
```

空接口可以保存任何类型的值（因为每个类型都至少实现了零个方法）。
空接口被用来处理未知类型的值。
例如`fmt.Print`可接受类型为`interface {}`的任意数量的参数。

### 3.类型断言

> 类型断言提供了访问接口值底层具体值的方式。

```
t := i.(T)
```

为了判断一个接口值是否保存了一个特定的类型，类型断言可返回两个值：其底层值和一个报告断言是否成功的布尔值。

```
t, ok := i.(T)
```

如果`i`保存了一个`T`，那么`t`将会是其底层值，而`ok`为`true`；否则`ok`将为`false`，而`t`为类型`T`的零值。

### 4.类型选择

> 类型选择是一种按顺序从几个类型断言中选择分支的结构。

与`switch`语句相似，`case`为类型。

```
switch v := i.(type) {    case T:    // v的类型为T    case S:    // v的类型为S    default:    // 没有匹配 v与i的类型相同}
```

### 5.Stringer

> `fmt`包中定义的`Stringer`是最普遍的接口之一。

```
fmt.Sprintf()package mainimport "fmt"type IPAddr [4]byte// TODO: 给 IPAddr 添加一个 "String() string" 方法func (ip IPAddr) String() string {	return fmt.Sprintf("%v.%v.%v.%v", ip[0], ip[1], ip[2], ip[3])}func main() {	hosts := map[string]IPAddr{		"loopback":  {127, 0, 0, 1},		"googleDNS": {8, 8, 8, 8},	}	for name, ip := range hosts {		fmt.Printf("%v: %v\n", name, ip)	}}
```

### 6.错误

> Go程序使用`error`值来表示错误状态。

`error`类型是一个内建接口：

```
type error interface {    Error() string}
```

**`error`为`nil`时表示成功，否则是失败。**

### 7. Reader

> `io`包指定了`io.Reader`接口，它表示从数据流的末尾进行读取。
> 在遇到数据流的结尾时，它会返回一个`io.EOF`错误。

```
func (T) Read(b []byte) (n int, err error)
```

### 8. 图像

> `image`包定义了`Image`接口。

```
package imagetype Image interface {    ColorModel() color.Model    Bounds() Rectangle    At(x, y int) color.Color}package mainimport (	"golang.org/x/tour/pic"	"image"	"image/color")type Image struct{}func (i Image) ColorModel() color.Model {	return color.RGBAModel}func (i Image) Bounds() image.Rectangle {	return image.Rect(0, 0, 200, 200)}func (i Image) At(x, y int) color.Color {	return color.RGBA{uint8(x), uint8(y), uint8(255), uint8(255)}}func main() {	m := Image{}	pic.ShowImage(m)}
```

## 五、并发

### 1.Go程

> Go程（goroutine）是由Go运行时管理的轻量级线程。

```
go f()
```

### 2.信道

> 信道是带有类型的管道，你可以通过它用信道操作符`<-`来发送或者接收值。

```
ch <- v // 将v发送至信道chv := <-ch // 从ch接收值并赋予v
```

和映射与切片一样，信道在使用前必须创建：

```
ch := make(chan int)package mainimport "fmt"func sum(s []int, c chan int) {    sum := 0    for _, v := range s {        sum += v    }    c <- sum // 将和送入c}func main() {    s := []int{7, 2, 8, -9, 4, 0}        c := make(chan int)    go sum(s[:len(s) / 2], c)    go sum(s[len(s) / 2:], c)    x, y := <-c , <-c // 从c中接收        fmt.Println(x, y)    // -5    // 17}
```

> 信道可以是**带缓冲的**。将缓冲长度作为第二个参数提供给`make`来初始化一个带缓冲的信道。

```
ch := make(chan int, 100)
```

### 3.range和close

> 发送者可通过`close`关闭一个信道来表示没有需要发送的值了。

接收者可以通过为接收表达式分配第二个参数来测试信道是否被关闭；若没有值可以接收且信道已被关闭，那么在执行完

```
v, ok := <-ch
```

之后`ok`会被设置为`false`。

循环`for i := range c`会不断从信道接收值，直到它被关闭。

> **只有发送者才能关闭信道。**向一个已经关闭的信道发送数据会引发程序恐慌（panic）。
> 信道与文件不同，**通常情况下无需关闭它们**。只有在必须告诉接收者不再有需要发送的值时才有必要关闭，例如终止一个`range`循环。

通过信道实现斐波那契数列:

```
package mainimport "fmt"func fibonacci(n int, c chan int) {    x, y := 0, 1    for i := 0; i < n; i++ {        c <- x        x, y = y, x + y    }    close(c)}func main() {    c := make(chan int, 10)    go fibonacci(cap(c), c)    for i := range c {        fmt.Println(i)    }}
```

### 4.select语句

> `select`语句使一个Go程可以等待多个通信操作。
> `select`会阻塞到某个分支可以继续执行为止，这时就会执行该分支。当多个分支都准备好时会随机选择一个执行。

```
package mainimport "fmt"func fibonacci(c, quit chan int) {    x, y := 0, 1    for {        select {            case c <- x:                x, y = y, x + y            case <-quit:                fmt.Println("quit")                return        }    }}func main() {    c := make(chan int)    quit := make(chan int)    go func() {        for i := 0; i < 10; i++ {            fmt.Println(<-c)        }        quit <- 0    }()    fibonacci(c, quit)    // 0 1 1 2 3 5 8 13 21 34 quit}
```

> 当`select`中的其它分支都没有准备好时，`default`分支就会执行。

为了在尝试发送或者接收时不发生阻塞，可以使用`default`分支：

```
select {    case i := <-c:    // 使用i    default:    // 从c中接收会阻塞时执行}package mainimport (    "fmt"    "time")func main() {    tick := time.Tick(1000 * time.Millisecond)    boom := time.After(5000 * time.Millisecond)    for {        select {            case <-tick:                fmt.Println("tick")            case <-boom:                fmt.Println("BOOM!")                return            default:                fmt.Println("     .")                time.Sleep(500 * time.Millisecond)        }    }}
```