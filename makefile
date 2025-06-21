SHELL := /bin/bash
ANSIBLE_VAULT_PASSWORD ?= $(shell bw get notes 7adca851-b1aa-41d9-949d-b301011026a2)
LOCAL_BECOME_ROOT_PASSWORD ?= $(shell bw get notes b1fc68e1-9f91-4e79-bc2c-b303014cc1c4)

server-setup:
	@ANSIBLE_BECOME_PASSWORD="$(LOCAL_BECOME_ROOT_PASSWORD)" ansible-playbook \
		-i inventory.yml main.yml \
		--vault-password-file <(echo "$(ANSIBLE_VAULT_PASSWORD)") $(ARGS)

server-diff:
	@ANSIBLE_BECOME_PASSWORD="$(LOCAL_BECOME_ROOT_PASSWORD)" ansible-playbook \
		-i inventory.yml main.yml \
		--vault-password-file <(echo "$(ANSIBLE_VAULT_PASSWORD)") \
		--check --diff $(ARGS)

encrypt:
	@ansible-vault encrypt_string \
		--vault-password-file <(echo "$(ANSIBLE_VAULT_PASSWORD)") \
		--prompt $(ARGS)
