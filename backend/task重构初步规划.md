我刚刚创建了我后端项目中关于定时任务的一些文件，使用APscheduler+RabbitMQ+Celery。
目前有下面5个核心文件:
backend\app\core\scheduler.py :只负责使用APscheduler 进行调度
backend\app\core\event_recorder.py :只负责将调度事件和celery的执行事件记录到数据库。
backend\app\core\task_dispatcher.py :只负责注册任务并且将任务分发到celery
backend\app\core\job_config_manager.py :只负责管理任务的配置信息。
backend\app\services\tasks_manager.py :协调上面4个组件，作为用户输入的入口

可以看到，我的上面5个文件中，都写死了目前任务的类型，比如cleanup，或者scraping。（目前我的系统中只有这两种类型的任务）
可是，我的系统随着规模的增长，会增加越来越多的任务，比如send_email,notification 的新类型。
因此，目前的代码缺乏良好的扩展性。

我现在希望搭建一个框架，能够随时创建，修改不同类型的定时任务，同时监控任务状态，纪律任务执行履历。
为了完善这个框架，我觉得需要添加和修改如下的文件。
-------------------------------------
第一部分:
1.
在backend\app\core 文件夹下 创建task_type.py文件，创建一个枚举类，用来储存不同类型任务。
在backend\app\schemas 文件夹下创建task_type_schema.py文件，因为不同类型的task的配置参数不同，可能需要不同的schema对应。
2.
在backend\app\models 文件夹下增加一张task_config 表。
用来储存不同类型tasks的参数。
需要包含一个叫做task_type的列，类型为枚举，从上面创建的枚举类中取值。
因为不同类型tasks的参数可能完全不同，你可能需要一个json类型的列用来存储配置参数。

3.目前backend\app\models\schedule_event.py 表用来储存调度时间相关的信息。
backend\app\models\task_execution.py 表用来储存celery中执行的任务的相关信息。

我想将这两张表与上面的task_config 表关联。为此请你考虑一下这三个表之间的关系，给出一种合理的设计
-------------------------------------
第二部分:
基础的数据库已经创建完成，接下来你可能需要针对这三个表建成各自的crud文件。
在backend\app\crud 文件夹下。
schedule_event.py与task_execution.py 对应的crud文件已经存在了，但是由于刚才你可能更改了数据库结构，所以这两个文件也要做相应的修改
然后创建task_config 表 相关的crud文件。
-------------------------------------
第三部分:
task相关的表与crud操作已经完成，现在需要你修改与tasks相关的4个核心组件。
backend\app\core\scheduler.py :只负责使用APscheduler 进行调度
backend\app\core\event_recorder.py :只负责将调度事件和celery的执行事件记录到数据库。
backend\app\core\task_dispatcher.py :只负责注册任务并且将任务分发到celery
backend\app\core\job_config_manager.py :只负责管理任务的配置信息。

注意这4个单纯组件的职责分离，不要有相互耦合。去掉代码中原本与cleanup和scraping相关的死代码。现在所有任务的都应该从task_config 表中读取然后注册。
然后你可能需要修改一下job_config_manager.py 增加相关的数据库操作，因为task_config 表是刚刚添加的。
-------------------------------------
第四部分:
现在与tasks相关的基本框架已经完成，接下来需要制作用户接口暴露给用户。
修改backend\app\services\tasks_manager.py，用来协调上面的4个组件。
至少需要有以下功能:
a.根据现有的task类型，创建一个task schedule
b.更新目前task schedule的配置参数
c.删除一个task schedule
d.立即批量执行多个 task schedule
剩下的还有查看task状态，执行状态，健康度等等功能，你可以参考现有的代码自行发挥
-------------------------------------
补充:如果要添加新类型的任务，首先在backend\app\tasks 文件夹下创建新的任务处理逻辑
然后在刚才创建的task_type.py枚举文件中，创建新的类型。