import asyncore

from direct.showbase.ShowBase import ShowBase
from direct.actor.Actor import Actor
from panda3d.bullet import BulletCapsuleShape, BulletCharacterControllerNode, BulletPlaneShape, BulletRigidBodyNode, \
    BulletWorld, ZUp
from panda3d.core import AmbientLight, DirectionalLight, Point3, VBase4, Vec3, deg2Rad
from pandac.PandaModules import loadPrcFile

from ..scene import Scene

loadPrcFile("client-config.prc")

class Thing(object):
    __things = {}

    @classmethod
    def add(self, tag, node, node_path):
        thing = Thing()
        Thing.__things[tag] = thing
        thing.tag = tag
        thing.node = node
        thing.node_path = node_path

    def remove(self):
        del Thing.__things[self.tag]

    @classmethod
    def get_thing(self, tag):
        return self.__things[tag]

class FriendlyFruit(ShowBase, Scene):
    def __init__(self, server_connection, player_tag):
        ShowBase.__init__(self)
        self.__server_connection = server_connection
        self.__player_tag = player_tag
        self.__rotations = {}

        # Panda pollutes the global namespace.  Some of the extra globals can be referred to in nicer ways
        # (for example self.render instead of render).  The globalClock object, though, is only a global!  We
        # create a reference to it here, in a way that won't upset PyFlakes.
        self.globalClock = __builtins__["globalClock"]

        # Turn off the debugging system which allows the camera to be adjusted directly by the mouse.
        self.disableMouse()

        # Set up physics: the ground plane and the capsule which represents the player.
        self.world = BulletWorld()

        # The ground first:
        shape = BulletPlaneShape(Vec3(0, 0, 1), 0)
        node = BulletRigidBodyNode("Ground")
        node.addShape(shape)
        np = self.render.attachNewNode(node)
        np.setPos(0, 0, 0)
        self.world.attachRigidBody(node)

        # Enable shader generation (for more sophisticated lighting etc.)
        self.render.setShaderAuto()

        # Create lights so we can see the scene.
        dlight = DirectionalLight("dlight")
        dlight.setColor(VBase4(2, 2, 2, 0))
        dlnp = self.render.attachNewNode(dlight)
        dlnp.setHpr(0, -60, 0)
        self.render.setLight(dlnp)

        alight = AmbientLight('alight')
        alight.setColor(VBase4(0.75, 0.75, 0.75, 0))
        alnp = self.render.attachNewNode(alight)
        self.render.setLight(alnp)

        # Create a task to update the scene regularly.
        self.taskMgr.add(self.update, "UpdateTask")

    # Update the scene by turning objects if necessary, and processing physics.
    def update(self, task):
        asyncore.loop(timeout=0.01, use_poll=True, count=1)

        for node, angular_velocity in self.__rotations.iteritems():
            node.setAngularMovement(angular_velocity)

        dt = self.globalClock.getDt()
        self.world.doPhysics(dt)
        return task.cont

    def server_created_object(self, tag, height, radius):
        # This shape is used for collision detection, preventing the player falling through the ground for
        # example.
        shape = BulletCapsuleShape(radius, height - 2 * radius, ZUp)

        # A character controller is a physical body which responds instantly to keyboard controls.  (Bodies
        # which respond to forces are difficult to control in a satisfactory way using typical video game
        # controls.  Players expect them to move instantly when a button is pressed, but physics dictates that
        # they should take a short time to accelerate.)
        node = BulletCharacterControllerNode(shape, 0.4, tag)
        node_path = self.render.attachNewNode(node)
        Thing.add(tag, node, node_path)
        self.world.attachCharacter(node)

        # Does this object represent the player who is using this client?
        if tag == self.__player_tag:
            # If yes, attach the camera to the object, so the player's view follows the object.
            self.camera.reparentTo(node_path)
        else:
            # If no, create a new Actor to represent the player or NPC.
            humanoid = Actor("player.bam")
            humanoid.setH(180)
            humanoid.reparentTo(node_path)

            # Scale the Actor so it is the same height as the bounding volume requested by the server.
            point1 = Point3()
            point2 = Point3()
            humanoid.calcTightBounds(point1, point2)
            humanoid.setScale(height / (point2.z - point1.z))

            # If the 3D model has the origin point at floor level, we need to move it down by half the height
            # of the bounding volume.  Otherwise it will hang in mid air, with its feet in the middle of the
            # bounding volume.
            humanoid.setZ(-height / 2)

    def server_removed_object(self, tag):
        thing = Thing.get_thing(tag)
        self.world.removeCharacter(thing.node)
        thing.node_path.removeNode()
        thing.remove()

    def server_moves_thing(self, tag, loc_x, loc_y, loc_z, speed_x, speed_y, speed_z, angle, angular_velocity):
        thing = Thing.get_thing(tag)
        thing.node_path.setPos(loc_x, loc_y, loc_z)
        thing.node.setLinearMovement(Vec3(speed_x, speed_y, speed_z), True)

        # I don't know why deg2Rad is required in the following line; I suspect it is a Panda bug.
        thing.node_path.setH(deg2Rad(angle))

        if angular_velocity != 0:
            self.__rotations[thing.node] = angular_velocity
        elif thing.node in self.__rotations:
            del self.__rotations[thing.node]
