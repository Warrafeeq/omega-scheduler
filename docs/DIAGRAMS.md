# Omega Architecture Diagrams

## 1. High-Level System Architecture

```

                         OMEGA CLUSTER SCHEDULER                      


                              
                                 Users     
                                 Submit    
                                  Jobs     
                              
                                     
                    
                                                    
                                                    
             
             Batch          Service        MapReduce   
           Scheduler       Scheduler       Scheduler   
                                                       
          - Fast          - Sophisti-     - Opportun-  
          - Throughput      cated           istic      
          - 10ms/job      - Reliable      - Scaling    
             
                                                   
                    1. Get Snapshot                 
                
                                  
                    
                       SHARED CELL STATE      
                                              
                      - Optimistic Locking    
                      - Version Control       
                      - Transaction Log       
                      - Conflict Detection    
                    
                                 
                    2. Make Placement Decisions
                                 
                    
                                              
                                              
               
             MACHINES                  JOBS        
                                                   
          - CPU, GPU, RAM         - Tasks          
          - Heterogeneous         - Dependencies   
          - Version #             - Priorities     
               
                                              
                    
                                 
                    3. Commit Transaction
                                 
                    
                       Conflict Resolution    
                                              
                     - Version Check          
                     - Resource Validation    
                     - Incremental Commit     
                    
```

## 2. Transaction Lifecycle

```

                    TRANSACTION LIFECYCLE                         


    Scheduler                Cell State              Machines
                                                       
          1. Request Snapshot                          
        >                       
                                                       
          2. Return Snapshot                           
        <                       
                                                       
          3. Make Decisions                            
          (Local Processing)                           
                                                       
          4. Submit Transaction                        
        >                       
                                                       
                                  5. Check Versions    
                                >
                                                       
                                  6. Validate Resources
                                <
                                                       
                                  7. Update State      
                                >
                                                       
          8. Commit Result                             
        <                       
                                                       
          [If Conflict]                                
          9. Retry with Fresh                          
             Snapshot                                  
                                                       
```

## 3. Conflict Detection and Resolution

```

                  CONFLICT DETECTION FLOW                         


                    Transaction Submitted
                            
                            
                
                  For Each Placement   
                
                            
                            
                
                  Check Machine Exists 
                
                            
                    
                                   
                   Yes             No
                                   
                                   
          
         Check Version        CONFLICT 
         machine.version     
         == expected?      
        
                
        
                       
       Yes             No
                       
                       
  
 Check           CONFLICT 
 Resources      
 Available?   

       

             
Yes          No
             
             
  
 OK      CONFLICT 
  

        RESOLUTION STRATEGY
        

  Incremental Transaction    
  (Default)                  
                             
  - Accept OK placements     
  - Reject conflicts         
  - Partial success          



  Gang Scheduling            
  (All-or-Nothing)           
                             
  - Any conflict = fail all  
  - Retry entire job         
  - Atomic guarantees        

```

## 4. Scheduler Decision Flow

```

                    SCHEDULER DECISION FLOW                       


                        Job Arrives
                            
                            
                
                  Get Cell Snapshot    
                
                            
                            
                
                  Analyze Job          
                  - Task count         
                  - Resource needs     
                  - Constraints        
                  - Priority           
                
                            
                            
                
                  Score Machines       
                  - Resource fit       
                  - Load balance       
                  - Failure domains    
                  - Constraints        
                
                            
                            
                
                  For Each Task        
                
                            
                            
                
                  Select Best Machine  
                  - Highest score      
                  - Meets constraints  
                  - Has resources      
                
                            
                            
                
                  Add to Transaction   
                  - Task -> Machine     
                  - Record version     
                
                            
                            
                
                  Update Local State   
                  (Optimistic)         
                
                            
                            
                
                  Submit Transaction   
                
                            
                    
                                   
                 Success        Conflict
                                   
                                   
                
              Done          Retry with  
                  Fresh       
                              Snapshot    
                            
```

## 5. Resource Model

```

                      RESOURCE MODEL                              


                        CLUSTER
                            
        
                                              
                                              
    Machine 1           Machine 2           Machine N
                    
     Type: A          Type: B          Type: C 
                    
     CPU: 8           CPU: 16          CPU: 8  
     GPU: 0           GPU: 0           GPU: 2  
     RAM: 16          RAM: 32          RAM: 32 
                    
     Alloc:           Alloc:           Alloc:  
     CPU: 4           CPU: 12          CPU: 6  
     GPU: 0           GPU: 0           GPU: 1  
     RAM: 8           RAM: 24          RAM: 20 
                    
     Avail:           Avail:           Avail:  
     CPU: 4           CPU: 4           CPU: 2  
     GPU: 0           GPU: 0           GPU: 1  
     RAM: 8           RAM: 8           RAM: 12 
                    
                                              
        
                            
                        TASKS
                            
        
                                              
                                              
    Task 1              Task 2              Task 3
                    
     CPU: 2           CPU: 4           CPU: 2  
     GPU: 0           GPU: 0           GPU: 1  
     RAM: 4           RAM: 8           RAM: 8  
                    
```

## 6. Workload Characteristics

```

                   WORKLOAD DISTRIBUTION                          


    BATCH JOBS (80%)              SERVICE JOBS (20%)
    
    Task Count                    Task Count
                                 
                         
                                 
    > Count          > Count
    Mean: 10, Std: 50             Mean: 5, Std: 10
    
    Duration                      Duration
                                 
                          
                                 
    > Time           > Time
    Mean: 5min, Std: 10min        Mean: 24h, Std: 12h
    
    Arrival Pattern               Arrival Pattern
                                 
                        
                                 
    > Time           > Time
    Exponential (λ=10s)           Exponential (λ=60s)
    
    Resource Needs                Resource Needs
    CPU: 2±1 cores                CPU: 4±2 cores
    GPU: 10% need 1               GPU: 5% need 1-2
    RAM: 4±2 GB                   RAM: 8±4 GB
```

## 7. Comparison: Monolithic vs Two-Level vs Omega

```

              SCHEDULER ARCHITECTURE COMPARISON                   


MONOLITHIC                TWO-LEVEL (Mesos)         OMEGA
                       
  Queue                   Resource               Batch   
                          Allocator             Scheduler
                          
 J1J2                                             
                       
                                        
                                                   
                       
                Sched    Sched    Sched        
                  A        B        C          
                       
                                                   
                     Offers                        
                               
                                                     
                       
 Single                 Partial              Full    
Scheduler                View                View    
                       
                                                   
                                                   
                       
 Cluster                Cluster             Cluster  
  State                  State               State   
                       

Concurrency:             Concurrency:          Concurrency:
  None                     Pessimistic           Optimistic
  (Serial)                 (Locks)               (Versions)

Visibility:              Visibility:           Visibility:
  Full                     Partial               Full
  (One view)               (Offers)              (Snapshot)

Blocking:                Blocking:             Blocking:
  Head-of-line            Offer wait            None
  (Sequential)            (Lock wait)           (Parallel)
```

## 8. Performance Metrics Dashboard

```

                    PERFORMANCE METRICS                           


THROUGHPUT                    LATENCY
Jobs/min                      Wait Time (s)
                             
                      
                      
                  
                  
                
  Mono 2Lvl Omega               Mono 2Lvl Omega

UTILIZATION                   CONFLICTS
Percentage                    Rate
                             
                          
                      
                  
                  
                
  CPU GPU  RAM                  Mono 2Lvl Omega

SCALABILITY                   FAIRNESS
Speedup                       DRF Score
                             
                             
                             
                             
                             
                
  50  100  500  1K              Mono 2Lvl Omega
  Machines
```

## 9. Failure Handling Flow

```

                    FAILURE HANDLING                              


                    Machine Failure
                            
                            
                
                  Detect Failure       
                  (Heartbeat timeout)  
                
                            
                            
                
                  Mark Machine Failed  
                
                            
                            
                
                  Get Tasks on Machine 
                
                            
                            
                
                  Release Resources    
                  - Update allocations 
                  - Increment version  
                
                            
                            
                
                  Notify Schedulers    
                  (Implicit via        
                   snapshot refresh)   
                
                            
                            
                
                  Reschedule Tasks     
                  - Find new machines  
                  - Submit transactions
                
                            
                            
                
                  Schedule Recovery    
                  (1-10 minutes)       
                
                            
                            
                
                  Machine Recovered    
                  - Mark available     
                  - Resume scheduling  
                
```

These diagrams provide visual representations of the Omega architecture, workflows, and key concepts. They complement the detailed documentation and help understand the system's design and operation.
