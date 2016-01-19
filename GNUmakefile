DOCKERFILE_DIR ?= point
IMAGE_NAME ?= private/point
CONTAINER_NAME ?= point
EXPOSE_TO ?= $(HOME)/point
CONFIG = config.mk

ifneq ("$(wildcard $(CONFIG))","")
	include $(CONFIG)
endif

# Записывает текущего юзера
# (потому что при выполнении от sudo его нельзя получить — каждая мейк-команда выполняется в сабшелле
# и ${USER} там `root`, если выполняется от sudo)
# и спрашивает коды рекапчи
configure:
	@rm -f $(CONFIG)
	@echo "USER=${USER}" > $(CONFIG)
	@echo "Get reCAPTCHA keys for domain point.local:"
	@echo https://www.google.com/recaptcha/admin
	@read -p 'Client-side integration code: ' RECAPTCHA_PUBLIC_KEY; \
		echo "RECAPTCHA_PUBLIC_KEY=$$RECAPTCHA_PUBLIC_KEY" >> $(CONFIG)
	@read -p 'Server-side integration code: ' RECAPTCHA_PRIVATE_KEY; \
		echo "RECAPTCHA_PRIVATE_KEY=$$RECAPTCHA_PRIVATE_KEY" >> $(CONFIG)

# Собирает образ с правильной таймзоной
image:
	@docker build --tag=$(IMAGE_NAME) \
		--build-arg timezone=$(shell cat /etc/timezone) \
		$(DOCKERFILE_DIR)

# Собирает контейнер
container:
	@docker run -p 80:80 -p 443:443 -p 5222:5222 -p 5223:5223 \
		--env YOUR_USER=$(USER) \
		--env OWNER_GROUP=$(shell id -g $(USER)) \
		--env OWNER_ID=$(shell id -u $(USER)) \
		--env RECAPTCHA_PUBLIC_KEY=$(RECAPTCHA_PUBLIC_KEY) \
		--env RECAPTCHA_PRIVATE_KEY=$(RECAPTCHA_PRIVATE_KEY) \
		--volume $(EXPOSE_TO):/home/point \
		--name $(CONTAINER_NAME) $(IMAGE_NAME)

start:
	@docker start $(CONTAINER_NAME)

login:
	@docker exec -t -i $(CONTAINER_NAME) /bin/bash
