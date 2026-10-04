(asdf:defsystem "image-agent"
  :description "Resumable, cooperative live SBCL image repair"
  :version "0.1.0" :serial t :components ((:file "src/kernel") (:file "src/properties")))
(asdf:defsystem "image-agent/store"
  :depends-on ("image-agent") :serial t
  :components ((:file "src/store") (:file "src/reference-world")))
(asdf:defsystem "image-agent/openai"
  :depends-on ("image-agent" "dexador" "yason" "babel")
  :components ((:file "src/openai")))
(asdf:defsystem "image-agent/cli"
  :depends-on ("image-agent/store" "image-agent/openai") :serial t
  :components ((:file "src/tools") (:file "src/chat") (:file "src/cli")))
(asdf:defsystem "image-agent/tests"
  :depends-on ("image-agent/store" "image-agent/cli" "fiveam" "check-it")
  :serial t :components ((:file "tests/suite") (:file "tests/cli-suite")))
