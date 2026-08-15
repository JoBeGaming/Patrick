# Patrick

ORE's Discord bot. Built as a replacement for [Chad](https://github.com/openRedstoneEngineers/chad).

## Running Patrick

### Prerequisites

Patrick uses the following software:

- [Python 3.12](https://www.python.org/downloads/release/python-31210/)
- Any python environment manager (I personally use pipenv) or buildah/podman to run as a container

### Creating a bot account

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click "New Application" and give it a name.
3. Navigate to "installation", uncheck "User install" and set "Install link" to "None".
4. Go to the "Bot" tab, disable "Public Bot" and enable all 3 intents (Presence, Server Members, and Message Content).
5. Click "Reset Token" to generate a bot token. Copy this token somewhere safe as we will need it later.
6. Go to the "OAuth2" tab, select "bot" and "applications.commands" under "Scopes", and then select the permissions you want to grant the bot. For ease of testing, you can select "Administrator" to give it all permissions. However, for production use, you should only select the permissions that are necessary for the bot to function.
7. Copy the generated URL at the bottom and paste it into your browser to invite the bot to your server.

### Getting the bot files

1. Clone the repository:

    ```bash
    git clone github.com/openRedstoneEngineers/patrick.git
    ```

2. Navigate to the cloned directory:

    ```bash
    cd patrick
    ```

3. Copy the example `.env.example` file to `.env`:

    ```bash
    cp .env.example .env
    ```

4. Open the `.env` file in a text editor (like nano or vim) and paste your bot token right after the `TOKEN=` line. It should look like this:

    ```plaintext
    TOKEN=abcdefghijklmnopqrstuvwxyz1234567890
    ```

5. Save the `.env` file.
6. Copy over the `config.example.yaml` to `config.yaml`:

    ```bash
    cp config.example.yaml config.yaml
    ```

7. Open the `config.yaml` file in a text editor and adjust any settings as needed. You will need to set the channels and roles correctly for your bot to start without errors. The other configurations can be left as default for now.
8. Install the dependencies. If using pip, the following command will install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

If you are using any python environment manager, you can use the equivalent command to install the dependencies from the `requirements.txt` file.

## Running through python directly

To run Patrick, you can use the following command, assuming you are in the root directory of the project and have set up your environment correctly:

```bash
python patrick.py
```

NOTE: If you are using a virtual environment, make sure to activate it before running the command.

## Running via Podman and Buildah

Build with buildah:

```bash
buildah bud -t patrick .
```

Run the container:

```bash
podman run -d --name patrick \
  --env-file .env \
  -v $(pwd):/app:Z \
  localhost/patrick
```

NOTE: Pushing changes to a deployed instance requires removing the `patrick` container, rebuilding Patrick, then rerunning it.

### Deployment

For deployment, create a systemd unit file:

```bash
podman generate systemd --name patrick \
  --restart-policy=always \
  --restart-sec=5 > patrick.service
```

Finally, save this unit file in the appropriate location and enable the service with the following commands:

```bash
sudo mv patrick.service /etc/systemd/system/
sudo systemctl enable patrick
sudo systemctl start patrick
```
