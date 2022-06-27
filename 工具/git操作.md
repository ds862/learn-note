## 1.Git 的数据模型

进行版本控制的方法很多。Git 拥有一个经过精心设计的模型，这使其能够支持版本控制所需的所有特性，例如维护历史记录、支持分支和促进协作。

### 快照

Git 将顶级目录中的文件和文件夹作为集合，并通过一系列快照来管理其历史记录。在Git的术语里，文件被称作Blob对象（数据对象），也就是一组数据。目录则被称之为“树”，它将名字与 Blob 对象或树对象进行映射（使得目录中可以包含其他目录）。快照则是被追踪的最顶层的树。例如，一个树看起来可能是这样的：

```
<root> (tree)
|
+- foo (tree)
|  | 
|  + bar.txt (blob) 
|
+- baz.txt (blob)
```

这个顶层的树包含了两个元素，一个名为 "foo" 的树（包含一个blob对象 "bar.txt"），以及一个 blob 对象 "baz.txt"。

### 历史记录建模：关联快照

版本控制系统和快照有什么关系呢？线性历史记录是一种最简单的模型，它包含了一组按照时间顺序线性排列的快照。不过处于种种原因，Git 并没有采用这样的模型。

在 Git 中，历史记录是一个由快照组成的有向无环图。有向无环图，听上去似乎是什么高大上的数学名词。不过不要怕，您只需要知道这代表 Git 中的每个快照都有一系列的“父辈”，也就是其之前的一系列快照。注意，快照具有多个“父辈”而非一个，因为某个快照可能由多个父辈而来。例如，经过合并后的两条分支。

在 Git 中，这些快照被称为“提交”。通过可视化的方式来表示这些历史提交记录时，看起来差不多是这样的：

```
o <-- o <-- o <-- o
            ^  
             \
              --- o <-- o
```

上面是一个 ASCII 码构成的简图，其中的 `o` 表示一次提交（快照）。

箭头指向了当前提交的父辈（这是一种“在。。。之前”，而不是“在。。。之后”的关系）。在第三次提交之后，历史记录分岔成了两条独立的分支。这可能因为此时需要同时开发两个不同的特性，它们之间是相互独立的。开发完成后，这些分支可能会被合并并创建一个新的提交，这个新的提交会同时包含这些特性。新的提交会创建一个新的历史记录，看上去像这样（最新的合并提交用粗体标记）：  

<pre class="highlight">
<code>
o <-- o <-- o <-- o <---- <strong>o</strong>
            ^            /
             \          v
              --- o <-- o
</code>
</pre>


Git 中的提交是不可改变的。但这并不代表错误不能被修改，只不过这种“修改”实际上是创建了一个全新的提交记录。而引用（参见下文）则被更新为指向这些新的提交。

### 数据模型及其伪代码表示

以伪代码的形式来学习 Git 的数据模型，可能更加清晰：

```
// 文件就是一组数据
type blob = array<byte>

// 一个包含文件和目录的目录
type tree = map<string, tree | blob>

// 每个提交都包含一个父辈，元数据和顶层树
type commit = struct {
    parent: array<commit>
    author: string
    message: string
    snapshot: tree
}
```

这是一种简洁的历史模型。

### 对象和内存寻址

Git 中的对象可以是 blob、树或提交：

```
type object = blob | tree | commit
```

Git 在储存数据时，所有的对象都会基于它们的 [SHA-1 哈希](https://en.wikipedia.org/wiki/SHA-1) 进行寻址。

```
objects = map<string, object>

def store(object):
    id = sha1(object)
    objects[id] = object

def load(id):
    return objects[id]
```

Blobs、树和提交都一样，它们都是对象。当它们引用其他对象时，它们并没有真正的在硬盘上保存这些对象，而是仅仅  保存了它们的哈希值作为引用。

例如，[上面](#snapshots)例子中的树（可以通过 `git cat-file -p 698281bc680d1995c5f4caaf3359721a5a58d48d` 来进行可视化），看上去是这样的：

```
100644 blob 4448adbf7ecd394f42ae135bbeed9676e894af85  baz.txt
040000 tree c68d233a33c5c06e0340e4c224f0afca87c8ce87  foo
```

树本身会包含一些指向其他内容的指针，例如 `baz.txt` (blob) 和 `foo`
(树)。如果我们用 `git cat-file -p 4448adbf7ecd394f42ae135bbeed9676e894af85`，即通过哈希值查看 baz.txt 的内容，会得到以下信息：

```
git is wonderful
```

### 引用

现在，所有的快照都可以通过它们的 SHA-1 哈希值来标记了。但这也太不方便了，谁也记不住一串 40 位的十六进制字符。

针对这一问题，Git 的解决方法是给这些哈希值赋予人类可读的名字，也就是引用（references）。引用是指向提交的指针。与对象不同的是，它是可变的（引用可以被更新，指向新的提交）。例如，`master` 引用通常会指向主分支的最新一次提交。

```
references = map<string, string>

def update_reference(name, id):
    references[name] = id

def read_reference(name):
    return references[name]

def load_reference(name_or_id):
    if name_or_id in references:
        return load(references[name_or_id])
    else:
        return load(name_or_id)
```

这样，Git 就可以使用诸如 "master" 这样人类可读的名称来表示历史记录中某个特定的提交，而不需要在使用一长串十六进制字符了。

有一个细节需要我们注意， 通常情况下，我们会想要知道“我们当前所在位置”，并将其标记下来。这样当我们创建新的快照的时候，我们就可以知道它的相对位置（如何设置它的“父辈”）。在 Git 中，我们当前的位置有一个特殊的索引，它就是 "HEAD"。

### 仓库

最后，我们可以粗略地给出 Git 仓库的定义了：`对象` 和 `引用`。

在硬盘上，Git 仅存储对象和引用：因为其数据模型仅包含这些东西。所有的 `git` 命令都对应着对提交树的操作，例如增加对象，增加或删除引用。

当您输入某个指令时，请思考一下这条命令是如何对底层的图数据结构进行操作的。另一方面，如果您希望修改提交树，例如“丢弃未提交的修改和将 ‘master’ 引用指向提交 `5d83f9e` 时，有什么命令可以完成该操作（针对这个具体问题，您可以使用 `git checkout master; git reset --hard 5d83f9e`）



## 2. 基础操作

- `git help <command>`: 获取 git 命令的帮助信息

- `git init`: 创建一个新的 git 仓库，其数据会存放在一个名为 `.git` 的目录下

- `git status`: 显示当前的仓库状态

- `git add <filename>`: 添加文件到暂存区

- `git commit`: 创建一个新的提交

    - 如何编写 [良好的提交信息](https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html)!
    - 为何要 [编写良好的提交信息](https://chris.beams.io/posts/git-commit/)

- `git log`: 显示历史日志

- `git log --all --graph --decorate`: 可视化历史记录（有向无环图）

    `git log --graph --oneline`

- `git diff <filename>`: 显示与暂存区文件的差异

- `git diff <revision> <filename>`: 显示某个文件两个版本之间的差异

- `git reset --hard commit_id` 版本回退

    `git reset --hard HEAD^`回退到上一个版本

- `git restore <file>` 撤回工作区的文件

- `git restore --staged <file>` 撤回暂存区的文件

- `git rm <file>` 从版本库中删除文件，并提交到暂存区

### 版本回退

HEAD 指向的版本就是当前版本，Git允许我们在版本的历史之间穿梭，命令`git reset --hard commit_id`(commit id即哈希值)  。参数--hard直接把工作区的内容也修改了，不加--hard的时候只是操作了暂存区，不影响工作区。因此使用--hard时需要注意。

```
git reset --hard HEAD^  # 回退到上一个版本。
# 使用 ^ 向上移动 1 个提交记录；使用 ~<num> 向上移动多个提交记录，如 ~3
```

* 穿梭前，用`git log`可以查看提交历史，以便确定要回退到哪个版本。

  查看简要`git log --pretty=oneline`、`git log --all --graph --decorate --oneline`

* 要重返未来的版本，可以用`git reflog`查看命令历史，以便确定要回到未来的哪个版本。

为了撤销更改并**分享**给别人，我们需要使用 `git revert`

### 工作区和暂存区概念

把文件往Git版本库里添加的时候，是分两步执行的：

第一步是用`git add`把文件添加进去，实际上就是把文件修改添加到暂存区；

第二步是用`git commit`提交更改，实际上就是把暂存区的所有内容提交到当前分支。

Git跟踪并管理的是修改，而非文件，每次修改，如果不用`git add`到暂存区，那就不会加入到`commit`中。

### 撤销修改

-  `git restore <file>`和`git checkout -- <file>`可以丢弃工作区的修改

1. 改乱了工作区某个文件的内容，想直接丢弃工作区的修改时（没有使用git add），用命令`git restore <file>`。

2. 不仅改乱了工作区某个文件的内容，还添加到了暂存区（使用了git add），想丢弃修改，分两步：

    第一步用命令`git restore --staged`或`git reset HEAD <file>` ，将暂存区的修改撤销掉（unstage），重新放回工作区。

    第二步`git restore <file>`

3. 已经提交了不合适的修改到版本库时，想要撤销本次提交，参考版本回退一节，不过前提是没有推送到远程库。

### 删除文件

从版本库中删除文件：`git rm <file>`

如果使用`rm <file>`删除了工作区中的文件，导致暂存区和工作区不一致，可以恢复：`git restore <file>`

使用`git rm <file>`删除了版本库和工作区中的文件，恢复：`git restore --staged <file>`

> 注意：从来没有被添加到版本库就被删除的文件，是无法恢复的！

##  3. 远程仓库

- `git remote`: 列出远端

- `git remote add <name> <url>`: 添加一个远端

- `git push <remote> <local branch>:<remote branch>`: 将对象传送至远端并更新远端引用

    如果本地分支名与远程分支名相同，则可以省略冒号,建议本地分支与远程同名，如：`git push origin master`、`git push origin dev`

- `git branch --set-upstream-to=<remote>/<remote branch> <local branch>`: 创建本地和远端分支的关联关系

- `git fetch`: 从远端获取对象/索引

- `git pull`: 相当于 `git fetch; git merge`

- `git clone`: 从远端下载仓库

### 本机关联Github

- 第1步：创建SSH Key。

    在用户主目录下，看看有没有.ssh目录，如果有，再看看这个目录下有没有`id_rsa`和`id_rsa.pub`这两个文件，如果已经有了，可直接跳到下一步。如果没有，打开Shell（Windows打开Git Bash），创建SSH Key： `ssh-keygen -t rsa -C "youremail@example.com"`

    之后可以在用户主目录里找到`.ssh`目录，里面有`id_rsa`和`id_rsa.pub`两个文件。

- 第2步：登陆GitHub，打开“Account settings”，“SSH Keys”页面，

    然后，点“Add SSH Key”，填上任意Title，在Key文本框里粘贴`id_rsa.pub`文件的内容。

### 添加/删除远程库

要关联一个远程库，使用命令`git remote add origin git@server-name:path/repo-name.git`

关联后，使用命令`git push -u origin main`第一次推送main分支的所有内容；此后，每次本地提交后，只要有必要，就可以使用命令`git push origin main`推送最新修改；

用`git remote rm <name>`命令删除远程库。使用前，建议先用`git remote -v`查看远程库信息：

### 从远程库克隆

`git clone`命令克隆

Git支持多种协议，包括`https`，但`ssh`协议速度最快

## 4. 分支管理

### 创建与合并分支

查看分支：`git branch`

创建分支：`git branch <name>` ` 

切换分支：`git switch <name>`   旧： `git checkout <name>`

创建+切换分支：`git switch -c <name>` `

合并某分支到当前分支：`git merge <revision>` 

删除分支：`git branch -d <name>` 

强制删除分支（未合并便删除）：`git branch -D <name>` 

`git mergetool`: 使用工具来处理合并冲突

`git rebase`: 将一系列补丁变基（rebase）为新的基线

### 解决冲突

当Git无法自动合并分支时，就必须首先解决冲突。解决冲突后，再提交，合并完成。

解决冲突就是把Git合并失败的文件手动编辑为我们希望的内容，再提交。

用`git log --graph`命令可以看到分支合并图。

查看分支合并情况:  `git log --graph --pretty=oneline --abbrev-commit`

### 分支管理策略

禁用`Fast forward`模式，Git就会在merge时生成一个新的commit，这样，从分支历史上就可以看出分支信息。`git merge --no-ff  dev <branch_name>`

**分支策略:**

`master`分支应该是非常稳定的，也就是仅用来发布新版本，平时不能在上面干活.活都在`dev`分支上，也就是说，`dev`分支是不稳定的，到某个时候，比如1.0版本发布时，再把`dev`分支合并到`master`上，在`master`分支发布1.0版本。

### Bug分支

当你接到一个修复一个代号101的bug的任务时，很自然地想创建一个分支`issue-101`来修复它，但是当前正在`dev`上进行的工作还没有提交。

`git stash`可以把当前工作现场“储藏”起来，等以后恢复现场后继续工作。

`git stash list`命令可以查看保存的工作现场。

有两个办法进行恢复：
一是用`git stash apply`恢复，但是恢复后，stash内容并不删除，你需要用`git stash drop`来删除；
另一种方式是用`git stash pop`，恢复的同时把stash内容也删了。

再用`git stash list`查看，就看不到任何stash内容了。

在master分支上修复了bug后，我们要想一想，dev分支是早期从master分支分出来的，所以这个bug其实在当前dev分支上也存在。

那怎么在dev分支上修复同样的bug？

同样的bug，要在dev上修复，我们只需要把`4c805e2 fix bug 101`这个提交所做的修改“复制”到dev分支。注意：我们只想复制`4c805e2 fix bug 101`这个提交所做的修改，并不是把整个master分支merge过来。

为了方便操作，Git专门提供了`git cherry-pick <commit_id>`命令，让我们能复制一个特定的提交到当前分支：

```
$ git branch
* dev
  master
$ git cherry-pick 4c805e2
[master 1d4b803] fix bug 101
 1 file changed, 1 insertion(+), 1 deletion(-)
```

Git自动给dev分支做了一次提交，注意这次提交的commit是`1d4b803`，它并不同于master的`4c805e2`，因为这两个commit只是改动相同，但确实是两个不同的commit。用`git cherry-pick`，我们就不需要在dev分支上手动再把修bug的过程重复一遍。

**小结**

修复bug时，我们会通过创建新的bug分支进行修复，然后合并，最后删除；

当手头工作没有完成时，先把工作现场`git stash`一下，然后去修复bug，修复后，再`git stash pop`，回到工作现场；

在master分支上修复的bug，想要合并到当前dev分支，可以用`git cherry-pick <commit_id>`命令，把bug提交的修改“复制”到当前分支，避免重复劳动。

### 多人协作

* 首先，可以试图用`git push origin <branch-name>`推送自己的修改；

* 如果推送失败，则因为远程分支比你的本地更新，需要先用`git pull`试图合并；

* 如果合并有冲突，则解决冲突，并在本地提交；

* 没有冲突或者解决掉冲突后，再用`git push origin <branch name>`推送就能成功！

    如果`git pull`提示`no tracking information`，则说明本地分支和远程分支的链接关系没有创建，用命令`git branch --set-upstream-to=<remote>/<remote branch> <local branch>`。

### Rebase

`git rebase`操作可以把分叉的提交历史“整理”成一条直线，看上去更直观.Rebase 实际上就是取出一系列的提交记录，“复制”它们，然后在另外一个地方逐个的放下去。

如在bugFix分支上执行`git rebase main`，可以将 bugFix  rebase 到 main分支上：

```
c1 <-- main            c1 <-- main <-- *bugFix
   <-- *bugFix
```

再切换到main分支上执行`git rebase bugFix`，变为

```
c1 <-- *main <-- bugFix          c1 <-- c2 <-- *main
                                               bugFix
```

也可以在main分支上直接执行`git rebase bugFix`，将bugFix合到main分支上：

```
c1 <-- *main            c1 <-- bugFix <-- *main
   <-- bugFix
```



## 标签管理

### 创建标签

- `git tag <tagname>`用于新建一个标签，默认为`HEAD`，也可以指定一个commit id，如`git tag v0.9 f52c633`；
- `git tag -a <tagname> -m "blabla..."`可以指定标签信息`-a`指定标签名，`-m`指定说明文字；
- `git tag`可以查看所有标签。
- `git show <tagname>`查看标签信息

### 操作标签

- 命令`git push origin <tagname>`可以推送一个本地标签；
- 命令`git push origin --tags`可以推送全部未推送过的本地标签；
- 命令`git tag -d <tagname>`可以删除一个本地标签；
- 命令`git push origin :refs/tags/<tagname>`可以删除一个远程标签。

`git describe <ref>`显示距离最近的标签，`<ref>` 可以是任何能被 Git 识别成提交记录的引用，如果你没有指定的话，Git 会以你目前所检出的位置（`HEAD`）。

它输出的结果是这样的：

```
<tag>_<numCommits>_g<hash>
```

`tag` 表示的是离 `ref` 最近的标签， `numCommits` 是表示这个 `ref` 与 `tag` 相差有多少个提交记录， `hash` 表示的是你所给定的 `ref` 所表示的提交记录哈希值的前几位。当 `ref` 提交记录上有某个标签时，则只输出标签名称。

如`git describe main` 输出`v1_2_gC2`

## 自定义git






## Git 高级操作

- `git config`: Git 是一个 [高度可定制的](https://git-scm.com/docs/git-config) 工具

- `git clone --depth=1`: 浅克隆（shallow clone），不包括完整的版本历史信息

- `git add -p`: 交互式暂存

- `git rebase -i`: 交互式变基

- `git blame`: 查看最后修改某行的人

    如` git blame _config.yml | grep collections`

- `git stash`: 暂时移除工作目录下的修改内容

- `git bisect`: 通过二分查找搜索历史记录

- `.gitignore`: [指定](https://git-scm.com/docs/gitignore) 故意不追踪的文件

## 资源

- [Pro Git](https://git-scm.com/book/en/v2) ，**强烈推荐**！学习前五章的内容可以教会您流畅使用 Git 的绝大多数技巧，因为您已经理解了 Git 的数据模型。后面的章节提供了很多有趣的高级主题。（[Pro Git 中文版](https://git-scm.com/book/zh/v2)）；
- [Oh Shit, Git!?!](https://ohshitgit.com/) ，简短的介绍了如何从 Git 错误中恢复；
- [Git for Computer Scientists](https://eagain.net/articles/git-for-computer-scientists/) ，简短的介绍了 Git 的数据模型，与本文相比包含较少量的伪代码以及大量的精美图片；
- [Git from the Bottom Up](https://jwiegley.github.io/git-from-the-bottom-up/)详细的介绍了 Git 的实现细节，而不仅仅局限于数据模型。好奇的同学可以看看；
- [How to explain git in simple words](https://smusamashah.github.io/blog/2017/10/14/explain-git-in-simple-words)；
- [Learn Git Branching](https://learngitbranching.js.org/) 通过基于浏览器的游戏来学习 Git ；
- 将 Git 集成到编辑器中好处多多。[fugitive.vim](https://github.com/tpope/vim-fugitive) 是 Vim 中集成 GIt 的常用插件