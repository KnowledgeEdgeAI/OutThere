# Serves the interactive OutThere prototype (index.html) on Cloud Run.
FROM nginx:1.27-alpine
RUN sed -i -e "s/listen  *80;/listen 8080;/" -e "s/listen  *\[::\]:80;/listen [::]:8080;/" /etc/nginx/conf.d/default.conf
COPY index.html outthere-v3-design.svg route-plan-preview.jpg first-draft.png /usr/share/nginx/html/
EXPOSE 8080
