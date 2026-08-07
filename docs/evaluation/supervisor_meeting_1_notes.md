Evaluating the learning methods on on a traffic environment 

The project: sandra: doing the work for over an year, doing experiments in the area, using the simulator,  doing experiments, stopping cars, its not possible, so we use the simulator, we have several ideas what you could do in the precise project but at this point, in the project, we do some exploratory work, we try tio understand the challenges and eventually we focus on a specific challenge, there are a lot of challenges randy has access the insfrastucutre to address the challenge, has code to tfind useful, this is why randy 

That is upto you, ive done projects in machine learning traffic forecasting, there isnt much in terms of apply on the data, but we have lots of different architecture, learning based, technologies that we haven ever tried, transformers, something you could possibly do. Incase you are interested evolves in terms of swe, a masters student is afraid of, project they dont produce a ot of stafteware but have the inclination of implement something in terms of substitution software, something you can do, data engineering platform for traffic predicting or traffic forecasting, presentitng of traffic information of the user, sense of data evolve it, customer information, people they people input data through mobile data, putting all the data together, data from traffic analysis, data from sensors, tdata from drivers, putting everything together, and coming out with a complete view of traffic as it is iat the moment somewhere, that would evolve more of a swe, data engineering, rather than forecasting, forecasting is just a part of it, what if scenarios, i assume you could be middle of it, what if the turn turn to this, if things change suddenly, this is just a possibility, we running a lot of work in this area, we are writing research papers, very welcome to 

Platform is also a project, from the business school, a publication, all we are doing together, running together, this adventure, there will be all research in publications, we are writing papers, we have so much work to do, platform is another, malaysia, people from india, huge group, working on the platform, so this is at the moment

We want to acquire the background, read paper, acquire of experience with the technology, try sumo the simulator, the want something more, data engineeeirng swe its fine, working with csf, university platform for learning, clusters, gpu, create an account on csf, randy use the platform very fomrotably, basically for doing the learning, first couple of weeks you are doing, reading the papers, anmd work with the infrastructure we use. And then, focusing on a spefiific challenge, 

Writing the paper is easier now, tools are make it easy us, complete a very good dissertation, start writing as soon as we working, how is that, everything you do, learni how to csf, how to work with sumo, building a data engineering platfor, with all kind of traffic data which is written in text, all of these things, will become sections in the dissertation, need to describe all the technology you are using, write the section, what is sumo, how do we use it, hwhat is the role of the sumo we want to work, this is the chance we want to start working, learning to use it, go with the details, write in work details, and towards in the end, put them together, we start writing as soon as we start working on the project, we accumjulate the project, notes thoughts question answers,we accumulate informatink knowledge from the paper we read, a ist of papers we can share with you, we have papers, so you can start reading them right away, in parallel you cna learn something these infreastutecure, playing with the infrastructure, we have some data to share if you would like, think of the dat engineering project, it is affiliated with research, these are all research project, as we are doing the work, you will be feeding us, material for writing research papers, wich you can author co author if they can use it

\=========ethan progress===============================

Understanding vec task offoaind and the transition to randy’e vec evn environment

What vec task offloading means

Introduction and purpose

Such as artificial cars, solve the problem of the in the future met this asian, so different cars have different computer level, so we all need to , vec task offloading actually involves and hte beginning 

Target scene connected autonomous vehicles and v2x

This is basically decision making, intelligent or not: vehicle roading units rus attached to edge servers and neighboring vehicles all have some computing and communication capability,, and neighboruing vehicles all have some computing and communication capability, in that setting selected application tasks, perceptron assistance, plattoning coridiationgs, cooperatringe aawareness meassage processing map of traffic information updates

@@@ task too heavy to be computed in a single bvechiel, in an meegency, cant be executed locally, it can be overloaded, another interesting whether the execution of the task depends on the data, external, the data, data not stored, not local computing information, if data is stored somewhere else, not in the car, not in the vechile, the task may need to travel where the data in needs, it might be cheaper to transfer the task vs transfer the data, the data is voluminous, very big, transferring the data would be expensive, can be dangerous, lose osme of it in the transmissin, some can be breached and even damaged and modified depending if its a if its private cant be transfereeded thee are things to consider, you are doing very well, 

He talks more about: transforming sources needed,, safety proble,s, 

Sandra says: ,missing from the report, references, 2 external sources, i assume you got this from papers, i think that, we need to cite the papers, we dont write academic work, or based on ai, ai makes a lot of mistakes, on rrela published work, you need to cite them, when you make an argument, you need to cite the sources, where the argument has been made before and cite that, paper needs to be published in reputable outlets, we dont cite wikipedia, it is not reputable, we only cite very strong published works, then we know that work has been scrutiinized and the community has accepted the idea, we get ideas from the research papers, you can use the idea to improve sentences wording that ai can do for us, but be very careful from not to go get ideas from ai, otherwise you will not give you the degree, 

Ethan question sandra answer: it is a masters dissertation, a 100 papers more or less, bit less or bit more, sources of information can be books, it is a big dissertation, we have tense and tense of references you will cite sumo, you will cite CSF, cite books where you have codesacks very well defined for you also cite research papers, otherwise it will look very suspicious, or you used generative ai tools to invalidate the work because the university will not accept arguments or ideas from ai,  this is a very useful exercise

What a task is input workload deadline result

Input data camera frame, batch of trajectory reports, a corporate awareness message in simulation this is rpesented by a data sze

Workload how much computation the task needs represented as CPU cycles

Deadline the time by which the result must be available safety related tasks have tight deadlines like 100ms coordinate tasks can be more ralex with 500ms

Output the requesting vehicle gets back a list of detected objects an updated ocridnation decision or a procecseed awareness message the result is usually uhc smaller than the input

What is transmitted during offloading when a task is offloaded what travels over the wireless link is the task’s input data, not a program and not a software object, the simulator esritmates the transmission time from the data size and the links current data rate, in my old propttype, only the upload was modelled with a fixed extra delay for reaching the cloud, the turn of the result was not modelled in randy environment my current understand is that the target processing and the turn of the result, the extract modelling details are something im still verifying as i read the code

What load means? Intensity of computational demands, how much task work arrives per unit time and not anything else, density in my old proptytple, load was varied through te task generation, … 0.5 to 1 or 2\.  Randy environment supports richer load variation…

The primilattry toy propttype and what it taught me, i built a small sumo trnci proptytpe, provided vehicle environment, synthetic task were generated from vehicle states and simple queueing and delay models computed latencies, the executing, the execution targets were local …

Algorithms and policiies, 

Fixed rules always local offload random  
Informed rules heursitiics hand written if the rules that at the task type the device capability and current load, cheap and transparent, but their thresholds are set by hand are shard to get

Lypunov lyapunov based control a method from network optimisation that scores each option by combing energy cost with the ffoect on queue growth it adapts to queue state without my training any training in both my prototype amnd my early tsersts on randy environment it is the stroingest non learning baseluine 

Reinforcement learning

Policies learning interaction and tabular q learning minimal learning baseline, dqn and ddqn a neural wntw0rk and mappo mappo additionally uses global information during training through not during executing the motivation for the mutli agent methods is that offloading decisions interact if every vehicle offloads at once the rus…

Why the old propttype isnt enough

Task were abstract tuples not groupned on real v2x app classes…

Transition to randy vec env

Address these gaps, and platform for the next stage at a high level

Scene a 2km highway with 209vehicle and 2 rsu cocnnteced to edge server

Three compute tiers for hetegroous vehicle category from a constrained raspberry pi class unit to a high end pgu equipped vehicle, will independently, combustion versus election propulsion,

Action space each vehicle decide per task among local v2i offload to an rus, and v2v offload to neghiboring vehicle

Task clases three types grounded in v2x application qeuirements t1 safety critical perception t2 platooning reporting heavy buoti with a relaxed deadline t2 is plattoning reporting t1 is safety critical perceptiomn t3 cooperative awareness messaging processing light and freuqeust

T1 is the class where offloading matters most, because a weak vehicle cannot finish it in locally

Algorithm lyapunus, tabous q dqn ddqn and muoti agent methods iipo mappo

Scaling path pytorth for local and much faster jax for large muti agent training with ready made scripts for the university csf custer, repo states theat the main mutli agent experiments should run on the other jax csf path

 Has gitlab access…. Readme, 

Current local familiarsation test… to check my setup and get a feel for the environment, i ran 2 small batches inm laptop, 

Local only is not unformationally bad, it complete light and relaxed task types fully but only about half of the safety critical t1 task, the weaker vehicle cannot finish t1 in time mathches intutiiton offloading excites mainly to rescue ciritcal tasks

Blind offloading is much worse not not offloading forcing everything on the rsu congests it and drops overall ocmpletion roughly a third 

Selective offloading win the lyapamuv baseline achieved the best completion in my small test while offloading fewer than one task inten it is  choosey about which tasks to send away

Learning works dqn ddqn start near random behavior and over 200 episodes move by themselves toward mostly local selectively offloadn the same shape the lypauv analysis suggests in right the mutli agent mtheods ippo mappo

Sandra hint: what we can do to make this more interesting, conclusion you are getting into, the task of offloading, is costly and the local computation is probably the best decision, how wever, this seems logical if i can run something in my local machine hy wou;ld i send it to a far away infrastructure to get it running for me, the results needs to be send back, no one in their perfect sense would do that, but int seems to be the scenarios, you have tested, never gave offloading a chance.. The scenarios you have been testing are so simple that local execution will always be the best choice, so this ist he danger of not having anything interesting to report, if everyhtung i test all the situations that i describe,e 20 vehicles in constant speed not far away from one another if you create very simple scenarioios, you will have very obvious outcomes, what you need to think about, is the situation ware, task of loading will be crucial so you will give a chance to the task of loading, task offloading??? A lot, it is not the case the task always run in the local [vehicle..if](http://vehicle..if) you are already getting the best outcome is the local execution you are not addressing all the challenges, you are convering all the possible with all the scenarios otherwise, multi agent may always be the best unless it is too expensive for hte task at hand, the most simple aogorutn will always be the best, it depends on the scenario, the most simple and least intelligent algortuhm always win, this is all you can report on the dissertation, the dissertation would be poor, all you have to say, the scenario is tested, the local execution is always the best, you will have a very poor dissertation to write because you havent explored the circumstances the setiatuons where the local exeuciton is not a good idea, it is not possible, need to think of all possible situations, different algorithms different decisions a chance to shine, poffloading the best decision here, rus, offloading to the cloud.. Offloading to the vehicle is another chance, a chance ot shine because if you only give the only obvious choices the obvious decisions, the local executions are the best, my scenario is the simple, the fastest onje to give me a decision… multi agent is complex and takes a long time to run,, then it will be a very poor dissertation to run, you need to come up with very complex diverse scenarios and okay

ETHAN question how ot build randy environment not criticising (sandra says) 

SANDRA: create scene to get interesting outcomes and interesting insights, theb est may not win, situation where interesting things can come up like morocco wins, things that they are expecting is not what the logic what the basic logic, the trivial , the eye can catch, is like, they want to go beyond, they want to investigate, events and details that  cna create situations interesting to analyze, morocco won, that everyone would be thinking what event what pass what idea they had t hat upset france that must be a textbook strategy, to upset a very strong football team, they want to write the bulk, the book that will create report insights ow to make a loser win, what are the situation where the worse algorithm would make it the best, the most intelligent will win, it is complex if its long, youneed a complex scenario, it will make the very interesting situation worthwhile, very cheap, not costly at all, the local decisions, will win, so…. This is what academics want to see, they want to see a big upset,  this is what we expect, research based, masters dissertation, from the papers, you will be a contribute coauthers with us, fingers crossed, an interesting narrative, the ovious outcome, mutli agent is clever, they will win or the local execution will always be the best.. This is what researchers dont want to hear because they are obvious, we want to see we want to see situations where this si not true and we know those situations exist, no matter if its urgent it cannot be executed locally, a vehicle is not a datacenter n the road by the side of the road we do have siome data centers they are not as big as power as the cloud but they are there and they are more powerful than any vehicle existing right now..maybe your mother grandmother will know by logic. Small task vs big computing task, executing the task in the vehicle would be best, want to go beyond common sense, common sens is not research, everybody knmows it

Data engineeitnv course, 

There is a third student taking the same project, maybe he will, i hope you will, not a good idea to do the project alone, try to do the data engineering project no progress to report, that is totally fine, invite to come in person, we can make it hybrid, it is completely i will never impose that to you, i like you to be comrortable have choices, use your creativity, dont want to impose things to you, you have some freedom, randy is learning to do that, 

Randy will share papers and infstractures and pepars, he has lots of share, the most improtat ones, dont overwhelm with too many papers, play with with the sumo, paly with some research papers, a little bit every week, how we go about devleloping a project for the university of m,anchester, she and randy has been studied here, britain have a time model, a time model calculates how much time you have to spend on your project, there is a calculation, the project is all you need to do, you can work full time, on your project, if you can work fulltime on your project when they read your dissertation, when they read it, they will expect a contribution that reflects that number of hours they calculated, if its hundreds of hours, they want a project that is substantial enough to reflect hundres of hours of work, and so this is where the advisor of supervisor is importantm, if you do something that t doesnt reflect this number of hours, a much smaller number of hours, they will give you a very good mark, so bear this mind, if you are given fulltime they expect you to work full time, i know you have may circumstances, you have have lots of things, work fulltime is 9 to 6 or 8 to 6, a full working day, in your country, parents work full time, work from morning and evening, take rests, take breaks, within the working hours, take breaks to exercise and eat, eat well, exercise well, this is the healthy routine, is working hard but taking breaks exercising, eating well, sleeping well, if you fall sickk, if you fall tired, burned out you will waste time, keep yourself sane and healthy to reach the end. Dont forget they will want something that represents full time work, you will need to work the whole day, whole working hours, everyday, to have a chance of having a good mark, so this is an advice, randy send them some papers and materials, information about hte infrastructure, we want to start right away, ehtan 

Sumo use it as a realistic mobility, ethan report, about hte environment, the environment to rep\[esent a realistic case, i actually test my learning methods in sumo, not using sumo because i want to know, really really make the training feasible because when you apply sumo it takes a long time, it is a different engine, at some point, i come up with idea (randy says) for the training phase that is an environment enough, not using sumo costly in training, strategy at the moment, training the model architecture and validate it with sumo simulation, and regarding with dr sandra we need to challenge the scenario, in environment increase the task arrival, the training budget, the point is, task arrival based on the recent related papers, the problem is that the drl in a simplistic environment, limited training budget, only 200 episodes, which is a fail, it is not a win for learning methods because this is not prompting the problem, the issue is not achieviing the task completion task completion rate how we can promote the task distribute, what ive found until now (randy kieeps saying() using a proper environment, we can have more training budgets, using lighter environment, using multi agents 3 hundred thousand episodes, in that amount of training budget the multi agent is able to achieve higher task completion rate with more balanced task distribution… more energy efificency, with only 200 episodes..the learnuing method is noit seeing the true balance of offloading decisions or systems scale, this is what ive found in the current research paper, what i address. How to fix the learning methodis,

Vehicle to everything is having so many use cases, search on the search engingine v2x, not only that, if not comfortable with that, you can find a data engineering topic, 

The system requires linux,, sumo also work best in linux, use a linux 

Read the paper, summarize the paper, and get the story and the background of the topics, start basically what you are going to do, you can have 3 options 1 or 2, dont make report too much, easily make notes for your own but keep it short concise, dr sandra can really know what you are focusing on, one or 2 stories, what about these, what do you think? What can i do this, number 1 and number 2, waht you will focus on, i highly recommend work on the research gaps, topic not only on task offloading but find another topic, based topic, one another topic, for literature review, use api to semantic scholar, how to request api to semantic scholar, tell your agent to use the api to to retrieve whatever papers ou need for the topic, give me the papers of this topic, top tier papers, waht are the research gaps, what can i do, what can i work on, most helpful to work on, like dr sandra said, whatever topic you want to do, based on wat least 1-2 paper future work, limitation for example so u can fill the gaps, and list the references, and what is the topic and what is it based on, what it is based on, so get the semantic scholar api, because if you do not have api the agent will fetch from the web and sometimes they get hallucinated, you can also use consensus, to do literature review, i usually ask agents to retrieve from the semantic scholar and consensus so he has a comprehensive results, ,remember to get the good paper, use the keyword top tier, from top tier journal, 