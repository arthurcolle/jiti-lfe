;;; An empty application for the launch demonstration.
;;; Load with: devenv shell -- image-repl --program examples/expense-tracker.lisp
;;; The caller supplies acceptance tests and safety rules, never application functions.
(in-package :cl-user)

(defun make-cli-world ()
  (let* ((world (image-agent:make-reference-world :initial '((:expenses . nil))))
         (table (image-agent:reference-table world))
         (package (image-agent:world-package world)))
    (labels ((application-function (name)
               (let ((symbol (find-symbol name package)))
                 (and symbol (fboundp symbol) (symbol-function symbol))))
             (with-fixture (function)
               ;; Goals execute on the owner worker and restore their own fixtures.
               (let ((checkpoint (funcall (image-agent:world-snapshot world))))
                 (unwind-protect
                      (progn
                        (setf (gethash :expenses table)
                              (copy-tree '((:amount 450 :category :coffee)
                                           (:amount 3200 :category :groceries)
                                           (:amount 1800 :category :transport))))
                        (funcall function))
                   (funcall (image-agent:world-restore world) checkpoint))))
             (category-totals-p (result)
               (and (listp result) (= (length result) 3)
                    (eql 450 (cdr (assoc :coffee result)))
                    (eql 3200 (cdr (assoc :groceries result)))
                    (eql 1800 (cdr (assoc :transport result))))))
      (list
       :id "expense-tracker" :world world
       :goals
       (list
        (cons :can-record-expenses
              (lambda ()
                (let ((add (application-function "ADD-EXPENSE")))
                  (and add
                       (with-fixture
                        (lambda ()
                          (setf (gethash :expenses table) nil)
                          (funcall add 450 :coffee)
                          (let ((entries (gethash :expenses table)))
                            (and (= (length entries) 1)
                                 (eql 450 (getf (first entries) :amount))
                                 (eq :coffee (getf (first entries) :category))))))))))
        (cons :correct-totals
              (lambda ()
                (let ((total (application-function "TOTAL-EXPENSES"))
                      (categories (application-function "SPENDING-BY-CATEGORY")))
                  (and total categories
                       (with-fixture
                        (lambda ()
                          (and (eql 5450 (funcall total))
                               (category-totals-p (funcall categories)))))))))
        (cons :correct-budget-report
              (lambda ()
                (let ((report (application-function "BUDGET-REPORT")))
                  (and report
                       (with-fixture
                        (lambda ()
                          (let ((value (funcall report 6000)))
                            (and (eql 5450 (getf value :spent))
                                 (eql 550 (getf value :remaining))
                                 (category-totals-p (getf value :by-category)))))))))))
       :invariants
       (list
        (cons :valid-expense-ledger
              (lambda ()
                (let ((expenses (gethash :expenses table)))
                  (and (listp expenses)
                       (every (lambda (entry)
                                (and (listp entry)
                                     (integerp (getf entry :amount))
                                     (plusp (getf entry :amount))
                                     (keywordp (getf entry :category))))
                              expenses)))))
        (cons :valid-report-entry-count
              (lambda ()
                (let ((count (gethash :report-entry-count table 0)))
                  (and (integerp count) (not (minusp count)))))))))))
