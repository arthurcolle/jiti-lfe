;;;; Pure bounded GOAP planner. Exported from tested live managed definitions.
(defmodule jiti_goap
  (export
   (goap-action 4)
   (goap-expand 8)
   (goap-matches 2)
   (goap-plan 5)
   (goap-replan 5)
   (goap-search 8)
   (goap-self-test 0)
   (goap-step 2)
   (goap-valid-action 1)
   (goap-valid-input 5)))

(define-function goap-action
  ()
  (lambda (id pre effects cost)
    (map 'id id 'pre pre 'effects effects 'cost cost)))

(define-function goap-expand
  ()
  (match-lambda 
    ((world cost path () queue seen budget clipped) (tuple queue seen clipped))
    ((world cost path (cons a rest) queue seen budget clipped)
     (case (goap-matches world (maps:get 'pre a))
       ('false (goap-expand world cost path rest queue seen budget clipped))
       ('true
        (let ((next (maps:merge world (maps:get 'effects a)))
              (total (+ cost (maps:get 'cost a))))
          (case (> total budget)
            ('true
             (goap-expand world cost path rest queue seen budget 'true))
            ('false
             (case (andalso
                    (maps:is_key next seen)
                    (=< (maps:get next seen) total))
               ('true
                (goap-expand world cost path rest queue seen
                 budget clipped))
               ('false
                (goap-expand world cost path rest
                 (cons
                  (tuple total (++ path (list (maps:get 'id a))) next)
                  queue)
                 (maps:put next total seen)
                 budget clipped)))))))))))

(define-function goap-matches
  ()
  (lambda (world conditions)
    (lists:all
     (lambda (kv)
       (let ((k (element 1 kv)) (v (element 2 kv)))
         (andalso (maps:is_key k world) (=:= (maps:get k world) v))))
     (maps:to_list conditions))))

(define-function goap-plan
  ()
  (lambda (world goal actions max-expansions max-cost)
    (case (goap-valid-input world goal actions max-expansions max-cost)
      ('false (map 'status 'invalid-input))
      ('true
       (goap-search
        (list (tuple 0 '() world))
        (maps:put world 0 #M())
        goal
        (lists:sort
         (lambda (a b) (< (maps:get 'id a) (maps:get 'id b)))
         actions)
        max-expansions max-cost 0
        'false)))))

(define-function goap-replan
  ()
  (lambda (observed-world goal actions max-expansions max-cost)
    (goap-plan observed-world goal actions max-expansions max-cost)))

(define-function goap-search
  ()
  (match-lambda 
    ((() seen goal actions limit budget expanded clipped)
     (map 'status (if clipped 'cost-limit 'unreachable) 'expanded expanded))
    (((cons entry rest) seen goal actions limit budget expanded clipped)
     (let ((cost (element 1 entry))
           (path (element 2 entry))
           (world (element 3 entry)))
       (case (> cost (maps:get world seen))
         ('true
          (goap-search rest seen goal actions limit budget expanded clipped))
         ('false
          (case (goap-matches world goal)
            ('true
             (map
              'status
              (if (=:= path '()) 'satisfied 'planned)
              'actions
              path
              'cost
              cost
              'predicted-world
              world
              'expanded
              expanded))
            ('false
             (case (>= expanded limit)
               ('true (map 'status 'expansion-limit 'expanded expanded))
               ('false
                (let ((r
                       (goap-expand world cost path actions
                        rest seen budget clipped)))
                  (goap-search
                   (lists:sort (element 1 r))
                   (element 2 r)
                   goal actions limit budget
                   (+ expanded 1)
                   (element 3 r)))))))))))))

(define-function goap-self-test
  ()
  (lambda ()
    (let* ((world #M(open false key false))
           (goal #M(open true))
           (get-key (goap-action 'get-key #M(key false) #M(key true) 1))
           (unlock
            (goap-action 'unlock #M(open false key true) #M(open true) 1))
           (force (goap-action 'force #M(open false) #M(open true) 5))
           (actions (list force unlock get-key))
           (r (goap-plan world goal actions 100 10)))
      (andalso
       (=:= (maps:get 'status r) 'planned)
       (=:= (maps:get 'cost r) 2)
       (=:= (maps:get 'actions r) '(get-key unlock))
       (=:= (maps:get 'predicted-world r) #M(open true key true))
       (=:= (maps:get 'status (goap-plan goal goal actions 0 0)) 'satisfied)
       (=:= (maps:get 'status (goap-plan world goal '() 10 10)) 'unreachable)
       (=:=
        (maps:get 'status (goap-plan world goal actions 0 10))
        'expansion-limit)
       (=:=
        (maps:get 'status (goap-plan world goal actions 100 1))
        'cost-limit)
       (=:= (maps:get 'status (goap-step world unlock)) 'precondition-failed)
       (=:=
        (maps:get 'world (goap-step world get-key))
        #M(open false key true))
       (=:=
        (maps:get
         'actions
         (goap-replan #M(open false key true) goal actions 100 10))
        '(unlock))
       (=:=
        (maps:get
         'status
         (goap-plan world goal (list (goap-action 'bad #M() #M() 0)) 10 10))
        'invalid-input)
       (=:=
        (maps:get
         'status
         (goap-plan world goal (list get-key get-key) 10 10))
        'invalid-input)
       (=:=
        (maps:get 'status (goap-plan world goal '(bad) 10 10))
        'invalid-input)
       (=:=
        (maps:get 'status (goap-plan world goal actions -1 10))
        'invalid-input)
       (=:= (goap-matches #M() #M(key false)) 'false)
       (=:=
        (maps:get
         'status
         (goap-plan
          #M(x false)
          #M(y true)
          (list
           (goap-action 'toggle #M(x false) #M(x true) 1)
           (goap-action 'back #M(x true) #M(x false) 1))
          100 10))
        'unreachable)
       (=:=
        (maps:get
         'actions
         (goap-plan
          #M()
          #M(done true)
          (list
           (goap-action 'b #M() #M(done true) 1)
           (goap-action 'a #M() #M(done true) 1))
          10 10))
        '(a))))))

(define-function goap-step
  ()
  (lambda (world action)
    (case (andalso (is_map world) (goap-valid-action action))
      ('false (map 'status 'invalid-input))
      ('true
       (case (goap-matches world (maps:get 'pre action))
         ('false (map 'status 'precondition-failed))
         ('true
          (map
           'status
           'predicted
           'world
           (maps:merge world (maps:get 'effects action)))))))))

(define-function goap-valid-action
  ()
  (lambda (a)
    (andalso
     (is_map a)
     (maps:is_key 'id a)
     (maps:is_key 'pre a)
     (maps:is_key 'effects a)
     (maps:is_key 'cost a)
     (is_map (maps:get 'pre a))
     (is_map (maps:get 'effects a))
     (is_integer (maps:get 'cost a))
     (> (maps:get 'cost a) 0))))

(define-function goap-valid-input
  ()
  (lambda (world goal actions expansions budget)
    (andalso
     (is_map world)
     (is_map goal)
     (is_list actions)
     (=< (length actions) 64)
     (lists:all (lambda (a) (goap-valid-action a)) actions)
     (=:=
      (length actions)
      (length
       (lists:usort (lists:map (lambda (a) (maps:get 'id a)) actions))))
     (is_integer expansions)
     (>= expansions 0)
     (=< expansions 10000)
     (is_integer budget)
     (>= budget 0))))

