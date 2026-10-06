;;;; Managed helpers developed by Jiti after reading the Farm design and actual APIs.
(defun plan-check (plan-id node-id)
  "Explicit stored-check verification of binary IDs using current plan version; execution is not verification."
  (let ((p (jiti_plan:inspect plan-id))) (jiti_plan:verify plan-id node-id (map-get p 'version))))

(defun plan-frontier (id)
  "Return current version and ordered ready tasks; readiness is not execution."
  (jiti_plan:ready id))

(defun plan-new (id title)
  "Create an empty durable plan with nonempty binary ID/title; starts no job."
  (jiti_plan:create id title))

(defun plan-run (plan-id node-id)
  "Explicit launch of a ready binary node ID with current plan version; stale mutations remain fenced."
  (let ((p (jiti_plan:inspect plan-id))) (jiti_plan:launch plan-id node-id (map-get p 'version))))

(defun plan-view (id) "Inspect a binary plan ID with derived statuses; no launch/reconcile." (jiti_plan:inspect id))

(defun process-adopt (handle)
  "Reconcile public handle under owner checks; adopt observed generation, never restart/replay. Persist returned handle if needed."
  (jiti_processes:reconcile handle))

(defun process-view (handle-or-id)
  "Observe public handle via inspect or binary job ID via status; no start/adoption."
  (if (is_binary handle-or-id) (jiti_processes:status handle-or-id) (jiti_processes:inspect handle-or-id)))
